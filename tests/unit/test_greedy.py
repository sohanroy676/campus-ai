import pytest
from builders import at, evolve, make_activity, make_campus, make_problem

from smartcampus.baselines.greedy import greedy
from smartcampus.domain.entities import Cohort, EquipmentPool, Faculty, Fault, SafetyHold
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.rules.base import RuleId
from smartcampus.rules.validator import validate
from smartcampus.solver.objective import StageValues, evaluate
from smartcampus.solver.solve import InfeasibleInputError, SolverSettings, solve

FAST = SolverSettings(stage_seconds=(5, 5, 5, 5, 5, 5))
TUE_10 = at(1, 10)
WHOLE_DAY = Interval(start=at(1, 8), end=at(1, 18))


def closed(*room_ids: str, interval: Interval = WHOLE_DAY) -> tuple[Fault, ...]:
    return tuple(Fault(id=f"fault-{r}", room_id=r, kind="ac", interval=interval) for r in room_ids)


def placed(plan_assignments: object, activity_id: str) -> tuple[str, int]:
    [a] = [a for a in plan_assignments if a.activity_id == activity_id]  # type: ignore[attr-defined]
    return a.room_id, a.start_min


def test_nothing_disrupted_keeps_every_class_where_it_was() -> None:
    problem = make_problem()
    plan = greedy(problem)
    assert placed(plan.assignments, "act1") == ("A1", TUE_10)
    assert plan.cancelled == frozenset() and plan.moves == ()
    assert evaluate(problem, plan) == StageValues(0, 0, 0, 0, 0, 0)


def test_a_closed_room_sends_the_class_to_the_nearest_free_option() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    plan = greedy(problem)
    assert placed(plan.assignments, "act1") == ("A2", TUE_10)  # same time, same building
    assert validate(problem, plan) == []


def test_a_class_that_fits_nowhere_is_cancelled() -> None:
    problem = evolve(make_problem(), faults=closed("A1", "A2", "B1"))
    plan = greedy(problem)
    assert plan.cancelled == frozenset({"act1"}) and plan.assignments == ()


def test_equipment_is_moved_in_and_arrives_before_class() -> None:
    problem = evolve(
        make_problem(activities=(make_activity(required_equipment={"gpu": 3}),)),
        faults=closed("A1"),
    )
    plan = greedy(problem)
    [move] = plan.moves
    assert (move.pool_id, move.activity_id, move.units) == ("gpu", "act1", 3)
    assert move.end_min == placed(plan.assignments, "act1")[1]
    assert validate(problem, plan) == []
    assert evaluate(problem, plan).cost == 3 * 5 + 15


def test_equipment_that_cannot_arrive_in_time_pushes_the_class_later() -> None:
    # Plan time 09:50 leaves 10 minutes; moving 3 gpus takes 30, so 10:00 is out of reach.
    problem = evolve(
        make_problem(activities=(make_activity(required_equipment={"gpu": 3}),)),
        faults=closed("A1"),
        plan_time_min=at(1, 9, 50),
    )
    plan = greedy(problem)
    _, start = placed(plan.assignments, "act1")
    assert start >= at(1, 10, 20)
    assert plan.moves[0].start_min >= problem.plan_time_min
    assert validate(problem, plan) == []


def test_it_does_not_look_ahead_so_an_early_class_can_cost_a_later_one_its_place() -> None:
    problem = squeeze_problem()
    greedy_plan, joint = greedy(problem), solve(problem, FAST)
    assert validate(problem, greedy_plan) == []
    assert greedy_plan.cancelled == frozenset({"b-second"})  # a-first took the only slot b needed
    assert joint.plan.cancelled == frozenset()  # the solver moves a-first to 11:00 instead
    assert evaluate(problem, greedy_plan) > joint.values


def squeeze_problem() -> RecoveryProblem:
    """Only A2 is usable 10:00-12:00. b-second must run at 10:00 (its teacher has a fixed class
    in B1 at 11:00); a-first can use any hour. a-first is handled first and takes 10:00."""
    window = Interval(start=at(1, 10), end=at(1, 12))
    fixed = make_activity(
        id="fixed",
        cohort_id="c3",
        faculty_ids=("f2",),
        room_id="B1",
        start_min=at(1, 11),
    )
    first = make_activity(id="a-first", cohort_id="c1", faculty_ids=("f1",), room_id="A1")
    second = make_activity(id="b-second", cohort_id="c2", faculty_ids=("f2",), room_id="B1")
    return make_problem(
        campus=make_campus(walk_ab=5),
        cohorts=(Cohort(id="c1", size=25), Cohort(id="c2", size=20), Cohort(id="c3", size=10)),
        faculty=(Faculty(id="f1"), Faculty(id="f2")),
        activities=(first, second, fixed),
        faults=(
            *closed("A1", interval=window),
            *closed("B1", interval=Interval(start=at(1, 10), end=at(1, 11))),
        ),
        movable_activity_ids=frozenset({"a-first", "b-second"}),
        window=window,
    )


def test_input_that_already_breaks_a_rule_is_reported_like_the_solver_does() -> None:
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
        greedy(clash)
    assert excinfo.value.rules == {RuleId.R2}


def test_nothing_to_recover_gives_an_empty_plan() -> None:
    plan = greedy(evolve(make_problem(), movable_activity_ids=frozenset()))
    assert plan.assignments == () and plan.cancelled == frozenset() and plan.moves == ()


def test_the_plan_carries_the_version_it_was_built_on() -> None:
    assert greedy(make_problem(), based_on_version=7).based_on_version == 7


def test_greedy_is_repeatable() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    assert greedy(problem) == greedy(problem)


def with_second_gpu_pool(units: int, required: int, **changes: object) -> RecoveryProblem:
    """A1 holds two gpu pools (4 and `units` gpus); the class needs `required` and A1 is closed."""
    campus = make_campus()
    spare = EquipmentPool(
        id="gpu-b", type="gpu", room_id="A1", units=units, movable=True, move_minutes_per_unit=5
    )
    return evolve(
        make_problem(
            campus=evolve(campus, pools=(*campus.pools, spare)),
            activities=(make_activity(required_equipment={"gpu": required}),),
        ),
        faults=closed("A1"),
        **changes,
    )


def test_one_pool_is_enough_when_it_covers_the_need() -> None:
    problem = with_second_gpu_pool(units=4, required=3)
    plan = greedy(problem)
    assert [(m.pool_id, m.units) for m in plan.moves] == [("gpu", 3)]  # same building, no spill
    assert validate(problem, plan) == []


def test_a_need_larger_than_one_pool_is_split_across_pools() -> None:
    problem = with_second_gpu_pool(units=4, required=6)
    plan = greedy(problem)
    assert sorted((m.pool_id, m.units) for m in plan.moves) == [("gpu", 4), ("gpu-b", 2)]
    assert validate(problem, plan) == []


def test_a_need_no_pool_can_meet_cancels_the_class() -> None:
    problem = with_second_gpu_pool(units=4, required=9)  # only 8 gpus exist in total
    assert greedy(problem).cancelled == frozenset({"act1"})


def test_a_pool_on_hold_cannot_be_moved_until_the_hold_ends() -> None:
    hold = SafetyHold(
        target_kind="equipment",
        target_id="gpu",
        interval=Interval(start=at(1, 8), end=at(1, 10, 30)),
    )
    problem = evolve(
        make_problem(activities=(make_activity(required_equipment={"gpu": 3}),)),
        faults=closed("A1"),
        holds=(hold,),
    )
    plan = greedy(problem)
    [move] = plan.moves
    assert move.start_min >= at(1, 10, 30)
    assert validate(problem, plan) == []
