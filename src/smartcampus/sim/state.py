"""State projection: a pure fold over the event log.

State version = number of events applied so far. The next event must carry exactly that number
as its `version`, and a `PlanApplied` is stale unless its plan was built on that same version.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace

from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.events import (
    Event,
    FaultOccurred,
    PlanApplied,
    RepairOverrun,
    SafetyHoldPlaced,
)
from smartcampus.domain.plan import Plan, PlanStatus
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval


class InvalidEventError(Exception):
    """The event cannot be appended to the log in its current state."""


class VersionConflictError(InvalidEventError):
    """The event's `version` is not the next number in the log."""


class StalePlanError(InvalidEventError):
    """The plan was built on a state older (or newer) than the log's current state."""


@dataclass(frozen=True)
class SimState:
    version: int = 0
    now_min: int = 0
    faults: tuple[Fault, ...] = ()
    holds: tuple[SafetyHold, ...] = ()
    applied_plans: tuple[Plan, ...] = ()

    def problem(self, base: RecoveryProblem) -> RecoveryProblem:
        """`base` with its faults and holds replaced by the ones this state knows about."""
        return RecoveryProblem.model_validate(
            {**dict(base), "faults": self.faults, "holds": self.holds}
        )


def apply_event(state: SimState, event: Event) -> SimState:
    """The state after `event`, or an `InvalidEventError` saying why it cannot be appended."""
    if event.version != state.version:
        raise VersionConflictError(
            f"event has version {event.version}, but the next version is {state.version}"
        )
    if event.at_min < state.now_min:
        raise InvalidEventError(
            f"event at minute {event.at_min} is before the clock at minute {state.now_min}"
        )
    advanced = replace(state, version=state.version + 1, now_min=event.at_min)
    match event:
        case FaultOccurred(fault=fault):
            if any(f.id == fault.id for f in state.faults):
                raise InvalidEventError(f"fault {fault.id} already occurred")
            return replace(advanced, faults=(*state.faults, fault))
        case RepairOverrun(fault_id=fault_id, new_end_min=new_end):
            return replace(advanced, faults=_extend_fault(state.faults, fault_id, new_end))
        case SafetyHoldPlaced(hold=hold):
            return replace(advanced, holds=(*state.holds, hold))
        case PlanApplied(plan=plan):
            if plan.based_on_version != state.version:
                raise StalePlanError(
                    f"plan was built on version {plan.based_on_version}, "
                    f"but the current state is version {state.version}"
                )
            applied = plan.model_copy(update={"status": PlanStatus.APPLIED})
            return replace(advanced, applied_plans=(*state.applied_plans, applied))
    raise AssertionError(f"unhandled event type {type(event).__name__}")  # pragma: no cover


def _extend_fault(faults: tuple[Fault, ...], fault_id: str, new_end: int) -> tuple[Fault, ...]:
    matching = [f for f in faults if f.id == fault_id]
    if not matching:
        raise InvalidEventError(f"repair overrun for unknown fault {fault_id}")
    [fault] = matching
    if new_end <= fault.interval.end:
        raise InvalidEventError(
            f"fault {fault_id} already lasts until minute {fault.interval.end}; "
            f"an overrun must end later, not at {new_end}"
        )
    longer = fault.model_copy(
        update={"interval": Interval(start=fault.interval.start, end=new_end)}
    )
    return tuple(longer if f.id == fault_id else f for f in faults)


def project(events: Iterable[Event]) -> SimState:
    """Replay a whole log from the empty state."""
    state = SimState()
    for event in events:
        state = apply_event(state, event)
    return state
