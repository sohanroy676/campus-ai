import json
from pathlib import Path

import pytest
from builders import asg, at, evolve, make_activity, make_plan, make_problem
from typer.testing import CliRunner

from smartcampus.cli import app
from smartcampus.coordinator.approval import Trigger
from smartcampus.coordinator.followups import FollowupError, load_followups
from smartcampus.coordinator.loop import recover
from smartcampus.coordinator.replan import replan_problem
from smartcampus.coordinator.run import Method
from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.events import (
    Approval,
    FaultOccurred,
    PlanApplied,
    RepairOverrun,
    SafetyHoldPlaced,
)
from smartcampus.domain.plan import PlanStatus
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.rules.validator import assert_valid
from smartcampus.sim.state import InvalidEventError, StalePlanError
from smartcampus.sim.store import EventStore
from smartcampus.solver.solve import SolverSettings

FAST = SolverSettings(stage_seconds=(5, 5, 5, 5, 5, 5))
FAULT = Fault(id="f1", room_id="A1", kind="ac", interval=Interval(start=at(1, 8), end=at(1, 12)))
OVERRUN = RepairOverrun(version=0, at_min=at(1, 9), fault_id="f1", new_end_min=at(1, 15))
EVENING = Interval(start=at(1, 11), end=at(1, 12))
DEMO = Path(__file__).parents[2] / "scenarios" / "dev"


def two_classes() -> RecoveryProblem:
    """act1 (A1, Tue 10:00) is hit by the fault; act2 (A1, Tue 13:00) only by an overrun."""
    act2 = make_activity(id="act2", cohort_id="c2", faculty_ids=("f2",), start_min=at(1, 13))
    return evolve(make_problem(activities=(make_activity(), act2)), faults=(FAULT,))


def with_hold(problem: RecoveryProblem) -> RecoveryProblem:
    hold = SafetyHold(
        target_kind="room", target_id="B1", interval=Interval(start=at(1, 8), end=at(1, 12))
    )
    return evolve(problem, holds=(hold,))


def test_a_cascade_replans_from_the_timetable_the_log_describes() -> None:
    with EventStore() as store:
        rounds = recover(two_classes(), store, Method.JOINT, [OVERRUN], settings=FAST)
        events = store.events()
    first, second = rounds
    assert first.plan.status is PlanStatus.APPLIED and first.approver == "not_needed"
    assert second.plan.status is PlanStatus.APPLIED
    assert [type(e) for e in events] == [FaultOccurred, PlanApplied, RepairOverrun, PlanApplied]
    assert [e.version for e in events] == [0, 1, 2, 3]
    assert second.plan.based_on_version == 3 and first.plan.based_on_version == 1
    # round 2 planned against the overrun fault and the clock of the overrun event
    assert second.problem.plan_time_min == at(1, 9)
    assert second.problem.faults[0].interval.end == at(1, 15)
    assert "act2" in second.problem.movable_activity_ids
    assert_valid(second.problem, second.planned.plan)


def test_a_class_moved_in_round_one_counts_as_moved_in_round_two() -> None:
    with EventStore() as store:
        rounds = recover(two_classes(), store, Method.JOINT, [OVERRUN], settings=FAST)
    second = rounds[1].problem
    first_plan = {a.activity_id: a for a in rounds[0].plan.assignments}
    moved = first_plan["act1"]
    assert (second.activity("act1").room_id, second.activity("act1").start_min) == (
        moved.room_id,
        moved.start_min,
    )
    assert second.prior_moves_this_week.get("c1") == 1


def test_a_trigger_is_auto_approved_in_demo_mode_and_logged() -> None:
    with EventStore() as store:
        [rnd] = recover(with_hold(two_classes()), store, Method.GREEDY)
        applied = [e for e in store.events() if isinstance(e, PlanApplied)]
    assert rnd.triggers == (Trigger.SAFETY_HOLD,) and rnd.approver == "auto"
    assert applied[0].approval == Approval(approver="auto", triggers=("safety_hold",))


def test_without_auto_approve_a_triggering_plan_waits_and_is_not_applied() -> None:
    with EventStore() as store:
        [rnd] = recover(with_hold(two_classes()), store, Method.GREEDY, auto_approve=False)
        assert not any(isinstance(e, PlanApplied) for e in store.events())
    assert rnd.plan.status is PlanStatus.PENDING_APPROVAL and rnd.approver is None


def test_an_event_arriving_before_approval_makes_the_pending_plan_stale() -> None:
    with EventStore() as store:
        rounds = recover(
            with_hold(two_classes()), store, Method.GREEDY, [OVERRUN], auto_approve=False
        )
        applied = [e for e in store.events() if isinstance(e, PlanApplied)]
    first, second = rounds
    assert first.plan.status is PlanStatus.STALE
    assert second.plan.status is PlanStatus.PENDING_APPROVAL
    assert applied == []
    assert second.plan.based_on_version == 3  # fault, hold and overrun, never a stale plan


def test_a_stale_plan_cannot_be_applied_by_hand() -> None:
    with EventStore() as store:
        recover(two_classes(), store, Method.GREEDY, [OVERRUN])
        old = make_plan(asg("act1", "A2", at(1, 10)))
        with pytest.raises(StalePlanError):
            store.append(PlanApplied(version=store.version, at_min=at(1, 9), plan=old))


def test_an_overrun_for_an_unknown_fault_is_refused_and_not_logged() -> None:
    bad = OVERRUN.model_copy(update={"fault_id": "nope"})
    with EventStore() as store:
        with pytest.raises(InvalidEventError):
            recover(two_classes(), store, Method.GREEDY, [bad])
        # round one's plan was applied; the bad event never reached the log
        assert [type(e) for e in store.events()] == [FaultOccurred, PlanApplied]


def test_an_overrun_that_does_not_extend_the_fault_is_refused() -> None:
    short = OVERRUN.model_copy(update={"new_end_min": at(1, 11)})
    with EventStore() as store, pytest.raises(InvalidEventError):
        recover(two_classes(), store, Method.GREEDY, [short])


def test_an_event_in_the_past_is_refused() -> None:
    early = OVERRUN.model_copy(update={"at_min": at(1, 7)})
    with EventStore() as store, pytest.raises(InvalidEventError):
        recover(two_classes(), store, Method.GREEDY, [early])


def test_two_overruns_in_a_row_replan_twice() -> None:
    later = OVERRUN.model_copy(update={"at_min": at(1, 10), "new_end_min": at(1, 17)})
    with EventStore() as store:
        rounds = recover(two_classes(), store, Method.GREEDY, [OVERRUN, later])
    assert len(rounds) == 3
    assert rounds[2].problem.faults[0].interval.end == at(1, 17)
    assert all(r.plan.status is PlanStatus.APPLIED for r in rounds)


def test_a_cancelled_class_stays_gone_in_later_rounds() -> None:
    problem = two_classes()
    with EventStore() as store:
        store.append(FaultOccurred(version=0, at_min=at(1, 8), fault=FAULT))
        store.append(
            PlanApplied(
                version=1,
                at_min=at(1, 8),
                plan=make_plan(cancelled=("act1",)).model_copy(update={"based_on_version": 1}),
            )
        )
        base = evolve(problem, faults=())
        rebuilt = replan_problem(base, store.state)
    assert {a.id for a in rebuilt.activities} == {"act2"}


def test_equipment_of_a_class_that_already_started_is_taken_as_delivered() -> None:
    gpu = make_activity(required_equipment={"gpu": 2}, start_min=at(1, 10))
    base = evolve(make_problem(activities=(gpu,)), faults=())
    plan = make_plan(asg("act1", "A2", at(1, 10))).model_copy(update={"based_on_version": 1})
    with EventStore() as store:
        store.append(FaultOccurred(version=0, at_min=at(1, 8), fault=FAULT))
        store.append(PlanApplied(version=1, at_min=at(1, 8), plan=plan))
        store.append(
            SafetyHoldPlaced(
                version=2,
                at_min=at(1, 10, 30),
                hold=SafetyHold(
                    target_kind="room",
                    target_id="B1",
                    interval=Interval(start=at(1, 11), end=at(1, 12)),
                ),
            )
        )
        rebuilt = replan_problem(base, store.state)
    assert rebuilt.activity("act1").required_equipment == {}
    assert rebuilt.activity("act1").room_id == "A2"
    assert "act1" not in rebuilt.movable_activity_ids  # it has started: it stays where it is


def test_the_window_grows_to_hold_a_moved_class_that_has_not_started() -> None:
    base = evolve(make_problem(), faults=())
    plan = make_plan(asg("act1", "A2", at(2, 9))).model_copy(update={"based_on_version": 1})
    with EventStore() as store:
        store.append(FaultOccurred(version=0, at_min=at(1, 8), fault=FAULT))
        store.append(PlanApplied(version=1, at_min=at(1, 8), plan=plan))
        rebuilt = replan_problem(base, store.state)
    assert "act1" in rebuilt.movable_activity_ids
    assert rebuilt.window.start <= at(2, 9) and rebuilt.window.end >= at(2, 18)


def test_followup_files_hold_disruption_events_only(tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps([{"type": "repair_overrun", "at_min": 5, "fault_id": "f1", "new_end_min": 9}])
    )
    assert load_followups(good) == [
        RepairOverrun(version=0, at_min=5, fault_id="f1", new_end_min=9)
    ]
    for name, text in {
        "plan": '[{"type": "plan_applied", "at_min": 0, "plan": {"based_on_version": 0}}]',
        "typo": '[{"type": "repair_overrun", "at_min": 5}]',
        "object": "{}",
        "item": "[1]",
        "json": "{",
    }.items():
        path = tmp_path / f"{name}.json"
        path.write_text(text)
        with pytest.raises(FollowupError):
            load_followups(path)
    with pytest.raises(FollowupError):
        load_followups(tmp_path / "missing.json")


def test_the_demo_cascade_moves_the_lab_class_again_after_the_overrun() -> None:
    from smartcampus.generator.scenario import load_scenario

    problem = load_scenario(DEMO / "ac-cascade.json")
    with EventStore() as store:
        rounds = recover(
            problem,
            store,
            Method.JOINT,
            load_followups(DEMO / "ac-cascade-overrun.json"),
            settings=SolverSettings(),
        )
    first, second = rounds
    assert first.values.people_moved == 26  # same as the single-disruption demo
    assert {a.activity_id: a.room_id for a in second.plan.assignments}[
        "robotics-lab"
    ] == "AI-Lab-02"
    assert second.values.cancellations == 0


runner = CliRunner()


def test_the_cascade_command_prints_each_round(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "cascade",
            str(DEMO / "ac-cascade.json"),
            "--followups",
            str(DEMO / "ac-cascade-overrun.json"),
            "--method",
            "greedy",
            "--db",
            str(tmp_path / "c.db"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Round 1 at Tue 08:00" in result.output and "Round 2 at Tue 12:00" in result.output
    assert "robotics-lab: AI-Lab-01 Tue 14:00 ->" in result.output
    assert "4 event(s)" in result.output


def test_the_cascade_command_rejects_a_bad_followup_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    result = runner.invoke(
        app,
        [
            "cascade",
            str(DEMO / "ac-cascade.json"),
            "--followups",
            str(bad),
            "--db",
            str(tmp_path / "c.db"),
        ],
    )
    assert result.exit_code == 2 and "not valid JSON" in result.output


def test_approval_is_validated_and_survives_a_round_trip_through_the_log() -> None:
    with pytest.raises(ValueError, match="not_needed"):
        Approval(approver="not_needed", triggers=("cancellation",))
    approval = Approval(approver="officer", triggers=("cancellation", "safety_hold"))
    plan = make_plan(cancelled=("act1",)).model_copy(update={"based_on_version": 0})
    with EventStore() as store:
        store.append(PlanApplied(version=0, at_min=0, plan=plan, approval=approval))
        [event] = store.events()
    assert isinstance(event, PlanApplied) and event.approval == approval


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_generated_scenario_survives_a_repair_overrun(seed: int) -> None:
    from smartcampus.generator.synth import generate_scenario

    problem = generate_scenario("small", 75, "room", seed)
    [fault] = problem.faults
    overrun = RepairOverrun(
        version=0,
        at_min=problem.plan_time_min,
        fault_id=fault.id,
        new_end_min=fault.interval.end + 240,
    )
    with EventStore() as store:
        rounds = recover(problem, store, Method.GREEDY, [overrun])
    assert len(rounds) == 2
    for rnd in (
        rounds
    ):  # `recover` re-checks every plan; this pins that the check ran on the rebuilt problem
        assert_valid(rnd.problem, rnd.planned.plan)
    assert rounds[1].problem.faults[0].interval.end == fault.interval.end + 240
