import pytest
from builders import at, evolve, make_activity, make_problem

from smartcampus.agents.contract_net import contract_net
from smartcampus.agents.resource import Bid, RoomAgent
from smartcampus.baselines.greedy import greedy
from smartcampus.coordinator.run import seed_disruptions
from smartcampus.domain.entities import Fault
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.generator.synth import generate_scenario
from smartcampus.rules.base import RuleId
from smartcampus.rules.validator import validate
from smartcampus.sim.store import EventStore
from smartcampus.solver.objective import StageValues, evaluate
from smartcampus.solver.solve import InfeasibleInputError

WHOLE_DAY = Interval(start=at(1, 8), end=at(1, 18))
LIMIT = 120.0


def closed(*room_ids: str) -> tuple[Fault, ...]:
    return tuple(Fault(id=f"fault-{r}", room_id=r, kind="ac", interval=WHOLE_DAY) for r in room_ids)


def as_logged(problem: RecoveryProblem) -> RecoveryProblem:
    """The problem as `run_scenario` plans it: faults and holds rebuilt from the event log."""
    base = RecoveryProblem.model_validate({**dict(problem), "faults": (), "holds": ()})
    with EventStore() as store:
        seed_disruptions(store, problem)
        return store.state.problem(base)


def test_nothing_disrupted_keeps_every_class_where_it_was() -> None:
    problem = make_problem()
    plan = contract_net(problem, time_limit_seconds=LIMIT)
    assert evaluate(problem, plan) == StageValues(0, 0, 0, 0, 0, 0)
    assert plan.cancelled == frozenset() and plan.moves == ()


def test_a_closed_room_sends_the_class_to_the_same_option_greedy_picks() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    plan = contract_net(problem, time_limit_seconds=LIMIT)
    assert validate(problem, plan) == []
    assert plan.assignments == greedy(problem).assignments


def test_a_class_that_fits_nowhere_is_cancelled() -> None:
    problem = evolve(make_problem(), faults=closed("A1", "A2", "B1"))
    plan = contract_net(problem, time_limit_seconds=LIMIT)
    assert plan.cancelled == frozenset({"act1"}) and plan.assignments == ()


def test_no_time_left_gives_a_valid_plan_that_cancels_what_was_not_awarded() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    plan = contract_net(problem, time_limit_seconds=0.0)
    assert validate(problem, plan) == []
    assert plan.cancelled == frozenset({"act1"})


def test_no_classes_to_recover_gives_an_empty_plan() -> None:
    plan = contract_net(
        evolve(make_problem(), movable_activity_ids=frozenset()), time_limit_seconds=LIMIT
    )
    assert plan.assignments == () and plan.cancelled == frozenset()


def test_input_that_already_breaks_a_rule_is_reported() -> None:
    clash = make_problem(
        activities=(
            make_activity(),
            make_activity(
                id="fixed1", cohort_id="c2", faculty_ids=("f2",), room_id="A2", start_min=at(1, 12)
            ),
            make_activity(
                id="fixed2", cohort_id="c1", faculty_ids=("f1",), room_id="A2", start_min=at(1, 12)
            ),
        ),
    )
    with pytest.raises(InfeasibleInputError) as excinfo:
        contract_net(clash, time_limit_seconds=LIMIT)
    assert excinfo.value.rules == {RuleId.R2}


def test_a_room_agent_bids_its_own_room_cheapest_first() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    agent = RoomAgent(problem.campus.room("A2"))
    bids = agent.bids(problem, problem.activity("act1"))
    assert bids and all(isinstance(b, Bid) and b.room_id == "A2" for b in bids)
    assert [b.cost for b in bids] == sorted(b.cost for b in bids)
    assert bids[0].start_min == at(1, 10)  # same time, no delay


def test_agents_bid_without_checking_rules_and_the_manager_refuses_invalid_bids() -> None:
    lab_only = make_activity(allowed_room_types=frozenset({"lab"}))
    problem = make_problem(activities=(lab_only,), faults=closed("A1"))
    assert RoomAgent(problem.campus.room("B1")).bids(
        problem, problem.activity("act1")
    )  # R4 not here
    plan = contract_net(problem, time_limit_seconds=LIMIT)
    assert validate(problem, plan) == []
    assert plan.cancelled == frozenset({"act1"})  # the only lab is closed


@pytest.mark.parametrize(
    ("load", "severity", "seed"), [(50, "room", 1), (90, "room", 2), (90, "hold", 2)]
)
def test_the_negotiated_plan_is_valid_and_never_worse_than_greedy(
    load: int, severity: str, seed: int
) -> None:
    problem = as_logged(generate_scenario("small", load, severity, seed))
    start = greedy(problem, based_on_version=2)
    plan = contract_net(problem, time_limit_seconds=LIMIT, based_on_version=2)
    assert validate(problem, plan) == []
    assert evaluate(problem, plan) <= evaluate(problem, start)


def test_re_auction_saves_a_class_greedy_cancelled() -> None:
    problem = as_logged(generate_scenario("small", 90, "hold", 2))
    greedy_values = evaluate(problem, greedy(problem, based_on_version=2))
    plan = contract_net(problem, time_limit_seconds=LIMIT, based_on_version=2)
    values = evaluate(problem, plan)
    assert greedy_values.cancellations == 2 and values.cancellations == 1
