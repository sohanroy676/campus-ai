import pytest
from builders import at
from pydantic import TypeAdapter, ValidationError

from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.events import (
    Event,
    FaultOccurred,
    PlanApplied,
    RepairOverrun,
    SafetyHoldPlaced,
)
from smartcampus.domain.plan import Plan
from smartcampus.domain.time import Interval

adapter: TypeAdapter[Event] = TypeAdapter(Event)

FAULT = Fault(id="f1", room_id="A1", kind="ac", interval=Interval(start=at(1, 10), end=at(1, 14)))
HOLD = SafetyHold(
    target_kind="room", target_id="A1", interval=Interval(start=at(1, 10), end=at(1, 14))
)


@pytest.mark.parametrize(
    "event",
    [
        FaultOccurred(version=1, at_min=at(1, 10), fault=FAULT),
        RepairOverrun(version=2, at_min=at(1, 13), fault_id="f1", new_end_min=at(1, 16)),
        SafetyHoldPlaced(version=3, at_min=at(1, 10), hold=HOLD),
        PlanApplied(version=4, at_min=at(1, 10), plan=Plan(based_on_version=3)),
    ],
)
def test_events_round_trip_through_the_discriminated_union(event: Event) -> None:
    restored = adapter.validate_json(adapter.dump_json(event))
    assert restored == event
    assert type(restored) is type(event)


def test_unknown_event_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "meteor", "version": 1, "at_min": 0})


def test_negative_version_rejected() -> None:
    with pytest.raises(ValidationError):
        RepairOverrun(version=-1, at_min=0, fault_id="f1", new_end_min=10)
