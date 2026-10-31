import json
from pathlib import Path

import pytest
from builders import at, evolve, make_activity, make_problem

from smartcampus.baselines.resolve import resolve_settings
from smartcampus.coordinator.run import Method, run_scenario, seed_disruptions
from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.events import FaultOccurred, PlanApplied, SafetyHoldPlaced
from smartcampus.domain.plan import PlanStatus
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.reporting.summary import format_minute, format_summary, report_dict, write_report
from smartcampus.rules.validator import validate
from smartcampus.sim.state import InvalidEventError
from smartcampus.sim.store import EventStore
from smartcampus.solver.solve import InfeasibleInputError, SolverSettings

FAST = SolverSettings(stage_seconds=(5, 5, 5, 5, 5, 5))
MORNING = Interval(start=at(1, 8), end=at(1, 12))
SCENARIO = Path("scenarios/test.json")


def disrupted(**changes: object) -> RecoveryProblem:
    fault = Fault(id="f1", room_id="A1", kind="ac", interval=MORNING)
    hold = SafetyHold(target_kind="room", target_id="B1", interval=MORNING)
    fields: dict[str, object] = {"faults": (fault,), "holds": (hold,), **changes}
    return evolve(make_problem(), **fields)


@pytest.mark.parametrize("method", list(Method))
def test_a_run_logs_the_disruption_then_applies_a_valid_plan(method: Method) -> None:
    problem = disrupted()
    with EventStore() as store:
        result = run_scenario(problem, method, store, FAST)
        events = store.events()
    assert [type(e) for e in events] == [FaultOccurred, SafetyHoldPlaced, PlanApplied]
    assert [e.version for e in events] == [0, 1, 2]
    assert result.log_version == 3
    assert result.plan.based_on_version == 2  # built on the state after both disruptions
    assert result.plan.status is PlanStatus.APPLIED
    assert validate(result.problem, result.plan) == []


@pytest.mark.parametrize("method", list(Method))
def test_the_problem_is_rebuilt_from_the_log_without_loss(method: Method) -> None:
    problem = disrupted()
    with EventStore() as store:
        assert run_scenario(problem, method, store, FAST).problem == problem


def test_only_the_solver_methods_report_stages_and_settings() -> None:
    with EventStore() as joint_store, EventStore() as greedy_store:
        joint = run_scenario(disrupted(), Method.JOINT, joint_store, FAST)
        greedy = run_scenario(disrupted(), Method.GREEDY, greedy_store)
    assert len(joint.stages) == 6 and joint.settings == FAST
    assert greedy.stages == () and greedy.settings is None


def test_resolve_reports_only_the_stages_it_runs() -> None:
    with EventStore() as store:
        result = run_scenario(disrupted(), Method.RESOLVE, store, FAST)
    assert [s.name for s in result.stages] == ["cancellations", "cost", "tie_break"]
    assert result.settings == resolve_settings(FAST)


def test_a_scenario_without_disruptions_plans_against_an_empty_log() -> None:
    with EventStore() as store:
        result = run_scenario(make_problem(), Method.JOINT, store, FAST)
        assert [type(e) for e in store.events()] == [PlanApplied]
    assert result.plan.based_on_version == 0
    assert result.values.people_moved == 0


def test_seeding_needs_an_empty_log() -> None:
    with EventStore() as store:
        seed_disruptions(store, disrupted())
        with pytest.raises(ValueError, match="empty event log"):
            seed_disruptions(store, disrupted())


def test_a_repeated_fault_id_is_refused() -> None:
    fault = Fault(id="same", room_id="A1", kind="ac", interval=MORNING)
    problem = evolve(make_problem(), faults=(fault, fault))
    with EventStore() as store, pytest.raises(InvalidEventError, match="already occurred"):
        run_scenario(problem, Method.GREEDY, store)


@pytest.mark.parametrize("method", list(Method))
def test_input_that_already_breaks_a_rule_has_no_plan(method: Method) -> None:
    clash = make_problem(
        activities=(
            make_activity(),
            make_activity(
                id="x", cohort_id="c2", faculty_ids=("f2",), room_id="A2", start_min=at(1, 12)
            ),
            make_activity(
                id="y", cohort_id="c1", faculty_ids=("f1",), room_id="A2", start_min=at(1, 12)
            ),
        ),
    )
    with EventStore() as store, pytest.raises(InfeasibleInputError):
        run_scenario(clash, method, store, FAST)
    # nothing but the failed attempt: no plan was applied
    with EventStore() as store:
        assert store.version == 0


@pytest.mark.parametrize(
    ("minute", "text"),
    [
        (0, "Mon 00:00"),
        (at(1, 10), "Tue 10:00"),
        (at(4, 17, 30), "Fri 17:30"),
        (at(6, 23, 59), "Sun 23:59"),
    ],
)
def test_format_minute(minute: int, text: str) -> None:
    assert format_minute(minute) == text


def test_the_summary_names_each_outcome() -> None:
    problem = disrupted(
        activities=(
            make_activity(required_equipment={"gpu": 2}),
            make_activity(
                id="gone", cohort_id="c2", faculty_ids=("f2",), room_id="B1", start_min=at(1, 14)
            ),
            make_activity(
                id="stays", cohort_id="c2", faculty_ids=("f2",), room_id="A2", start_min=at(1, 16)
            ),
        ),
        movable_activity_ids=frozenset({"act1", "gone", "stays"}),
        faults=(
            Fault(id="f1", room_id="A1", kind="ac", interval=MORNING),
            Fault(
                id="f2", room_id="A1", kind="ac", interval=Interval(start=at(1, 12), end=at(1, 18))
            ),
            Fault(
                id="f3", room_id="A2", kind="ac", interval=Interval(start=at(1, 14), end=at(1, 15))
            ),
            Fault(
                id="f4", room_id="B1", kind="ac", interval=Interval(start=at(1, 13), end=at(1, 18))
            ),
        ),
    )
    with EventStore() as store:
        result = run_scenario(problem, Method.JOINT, store, FAST)
    text = format_summary(result, SCENARIO, Path("var/campus.db"))
    assert "act1: A1 Tue 10:00 -> " in text
    assert "stays: unchanged (A2 Tue 16:00)" in text
    assert "equipment: 2 x gpu -> act1" in text
    assert "Hard rules R1-R8: all satisfied" in text
    assert "Method:     joint" in text and "4 fault(s), 1 hold(s)" in text


def test_a_cancelled_class_is_reported_as_cancelled() -> None:
    problem = evolve(
        make_problem(),
        faults=tuple(
            Fault(
                id=f"f-{r}", room_id=r, kind="ac", interval=Interval(start=at(1, 8), end=at(1, 18))
            )
            for r in ("A1", "A2", "B1")
        ),
    )
    with EventStore() as store:
        result = run_scenario(problem, Method.GREEDY, store)
    assert "act1: CANCELLED (was A1 Tue 10:00)" in format_summary(result, SCENARIO, Path("x.db"))
    assert report_dict(result, SCENARIO)["plan"]["cancelled"] == ["act1"]


def test_the_report_is_stable_json_without_timings(tmp_path: Path) -> None:
    problem = disrupted()
    texts = []
    for run in range(2):
        with EventStore() as store:
            result = run_scenario(problem, Method.JOINT, store, FAST)
        path = tmp_path / f"report{run}.json"
        write_report(result, SCENARIO, path)
        texts.append(path.read_text(encoding="utf-8"))
    assert texts[0] == texts[1]
    data = json.loads(texts[0])
    assert data["solver"]["random_seed"] == 42 and data["solver"]["num_workers"] == 1
    assert data["scenario"] == "scenarios/test.json" and data["method"] == "joint"
    assert set(data["stage_values"]) == set(data["stage_status"])
    assert "wall_time" not in texts[0] and '"seconds"' not in texts[0]
    assert texts[0].endswith("}\n") and "\r" not in texts[0]
