import pytest
from builders import asg, at, make_plan, make_problem

from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.events import (
    Event,
    FaultOccurred,
    PlanApplied,
    RepairOverrun,
    SafetyHoldPlaced,
)
from smartcampus.domain.plan import PlanStatus
from smartcampus.domain.time import Interval
from smartcampus.sim.state import (
    InvalidEventError,
    SimState,
    StalePlanError,
    VersionConflictError,
    apply_event,
    project,
)

MORNING = Interval(start=at(1, 8), end=at(1, 12))


def fault(fault_id: str = "f-a1", room: str = "A1", interval: Interval = MORNING) -> Fault:
    return Fault(id=fault_id, room_id=room, kind="ac", interval=interval)


def occurred(
    version: int, at_min: int = at(1, 8), fault_id: str = "f-a1", room: str = "A1"
) -> FaultOccurred:
    return FaultOccurred(version=version, at_min=at_min, fault=fault(fault_id, room))


def test_the_empty_log_is_version_zero() -> None:
    assert project([]) == SimState()
    assert SimState().version == 0


def test_a_fault_is_recorded_and_advances_the_version_and_clock() -> None:
    state = apply_event(SimState(), occurred(0, at_min=at(1, 9)))
    assert (state.version, state.now_min, state.faults) == (1, at(1, 9), (fault(),))


def test_a_repeated_fault_id_is_refused() -> None:
    state = apply_event(SimState(), occurred(0))
    with pytest.raises(InvalidEventError, match="already occurred"):
        apply_event(state, occurred(1))


def test_a_repair_overrun_extends_the_fault_interval() -> None:
    log: list[Event] = [
        occurred(0),
        RepairOverrun(version=1, at_min=at(1, 11), fault_id="f-a1", new_end_min=at(1, 15)),
    ]
    [extended] = project(log).faults
    assert extended.interval == Interval(start=at(1, 8), end=at(1, 15))
    assert extended.room_id == "A1"


@pytest.mark.parametrize("new_end", [at(1, 12), at(1, 10)])  # same end, or shorter
def test_an_overrun_must_end_later(new_end: int) -> None:
    state = apply_event(SimState(), occurred(0))
    overrun = RepairOverrun(version=1, at_min=at(1, 9), fault_id="f-a1", new_end_min=new_end)
    with pytest.raises(InvalidEventError, match="must end later"):
        apply_event(state, overrun)


def test_an_overrun_of_an_unknown_fault_is_refused() -> None:
    overrun = RepairOverrun(version=0, at_min=at(1, 9), fault_id="nope", new_end_min=at(1, 15))
    with pytest.raises(InvalidEventError, match="unknown fault"):
        apply_event(SimState(), overrun)


def test_a_safety_hold_is_recorded() -> None:
    hold = SafetyHold(target_kind="room", target_id="A2", interval=MORNING)
    state = apply_event(SimState(), SafetyHoldPlaced(version=0, at_min=at(1, 8), hold=hold))
    assert state.holds == (hold,)


@pytest.mark.parametrize("version", [1, 2, 99])
def test_a_skipped_version_is_refused(version: int) -> None:
    with pytest.raises(VersionConflictError):
        apply_event(SimState(), occurred(version))


def test_a_repeated_version_is_refused() -> None:
    state = apply_event(SimState(), occurred(0))
    with pytest.raises(VersionConflictError):
        apply_event(state, occurred(0, fault_id="other"))


def test_the_clock_never_runs_backwards() -> None:
    state = apply_event(SimState(), occurred(0, at_min=at(1, 10)))
    with pytest.raises(InvalidEventError, match="before the clock"):
        apply_event(state, occurred(1, at_min=at(1, 9), fault_id="late"))
    # the same minute is fine
    assert apply_event(state, occurred(1, at_min=at(1, 10), fault_id="same")).version == 2


def test_a_plan_built_on_the_current_version_is_applied_and_marked_applied() -> None:
    state = apply_event(SimState(), occurred(0))
    plan = make_plan(asg("act1", "A2", at(1, 10))).model_copy(update={"based_on_version": 1})
    state = apply_event(state, PlanApplied(version=1, at_min=at(1, 8), plan=plan))
    [applied] = state.applied_plans
    assert applied.status is PlanStatus.APPLIED
    assert applied.assignments == plan.assignments
    assert state.version == 2


def test_a_plan_on_the_empty_log_is_based_on_version_zero() -> None:
    plan = make_plan()
    assert plan.based_on_version == 0
    assert apply_event(SimState(), PlanApplied(version=0, at_min=0, plan=plan)).version == 1


@pytest.mark.parametrize("based_on", [0, 2, 5])  # older, or newer than the log
def test_a_plan_built_on_another_version_is_stale(based_on: int) -> None:
    state = apply_event(SimState(), occurred(0))  # version 1
    plan = make_plan().model_copy(update={"based_on_version": based_on})
    with pytest.raises(StalePlanError, match="current state is version 1"):
        apply_event(state, PlanApplied(version=1, at_min=at(1, 8), plan=plan))


def test_a_new_event_makes_an_earlier_plan_stale() -> None:
    plan = make_plan().model_copy(update={"based_on_version": 1})
    log: list[Event] = [
        occurred(0),
        RepairOverrun(version=1, at_min=at(1, 9), fault_id="f-a1", new_end_min=at(1, 15)),
    ]
    with pytest.raises(StalePlanError):
        project([*log, PlanApplied(version=2, at_min=at(1, 9), plan=plan)])


def test_a_refused_event_leaves_the_state_untouched() -> None:
    state = apply_event(SimState(), occurred(0))
    with pytest.raises(InvalidEventError):
        apply_event(state, occurred(5))
    assert state.version == 1 and len(state.faults) == 1


def test_the_problem_gets_the_faults_and_holds_of_the_state() -> None:
    hold = SafetyHold(target_kind="room", target_id="A2", interval=MORNING)
    state = project([occurred(0), SafetyHoldPlaced(version=1, at_min=at(1, 8), hold=hold)])
    problem = state.problem(make_problem())
    assert problem.faults == (fault(),)
    assert problem.holds == (hold,)
    assert problem.activities == make_problem().activities


def test_a_fault_in_an_unknown_room_is_caught_when_the_problem_is_built() -> None:
    state = project([occurred(0, room="Z9")])
    with pytest.raises(ValueError, match="unknown room"):
        state.problem(make_problem())
