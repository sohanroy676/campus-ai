from typing import Any

import pytest
from builders import at, make_activity, make_campus
from pydantic import ValidationError

from smartcampus.domain.entities import Building, Campus, Cohort, Room, Walk


def test_travel_is_symmetric_and_zero_within_a_building() -> None:
    campus = make_campus(walk_ab=7)
    assert campus.travel_minutes("A", "B") == 7
    assert campus.travel_minutes("B", "A") == 7
    assert campus.travel_minutes("A", "A") == 0


def test_lookups() -> None:
    campus = make_campus()
    assert campus.room("A2").capacity == 60
    assert campus.pool("gpu").movable
    with pytest.raises(KeyError):
        campus.room("nope")


def _campus_fields(**overrides: Any) -> dict[str, Any]:
    base = make_campus()
    fields: dict[str, Any] = {
        "buildings": base.buildings,
        "rooms": base.rooms,
        "pools": base.pools,
        "walks": base.walks,
    }
    fields.update(overrides)
    return fields


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"buildings": (Building(id="A"), Building(id="A"))}, "duplicate building"),
        (
            {"rooms": (Room(id="X", building_id="Z", type="lab", capacity=5, step_free=True),)},
            "unknown building",
        ),
        ({"walks": ()}, "every pair"),
        (
            {"walks": (Walk(a="A", b="B", minutes=1), Walk(a="B", b="A", minutes=1))},
            "duplicate walk",
        ),
        ({"walks": (Walk(a="A", b="A", minutes=0),)}, "distinct"),
        ({"walks": (Walk(a="A", b="Q", minutes=3),)}, "distinct, known"),
    ],
)
def test_campus_rejects_bad_references(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Campus(**_campus_fields(**overrides))


def test_single_building_campus_needs_no_walks() -> None:
    campus = Campus(
        buildings=(Building(id="A"),),
        rooms=(Room(id="A1", building_id="A", type="lab", capacity=5, step_free=True),),
    )
    assert campus.travel_minutes("A", "A") == 0


@pytest.mark.parametrize("size", [0, -3])
def test_cohort_size_must_be_positive(size: int) -> None:
    with pytest.raises(ValidationError):
        Cohort(id="c", size=size)


def test_models_are_frozen_and_forbid_extras() -> None:
    cohort = Cohort(id="c", size=5)
    with pytest.raises(ValidationError):
        cohort.size = 6  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Cohort(id="c", size=5, colour="red")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_min": at(1, 10, 15)},  # unaligned
        {"start_min": at(1, 17), "duration_slots": 3},  # ends 18:30
        {"start_min": at(5, 9)},  # Saturday
        {"duration_slots": 0},
        {"allowed_room_types": frozenset()},
        {"faculty_ids": ("f1", "f1")},
        {"required_equipment": {"gpu": 0}},
    ],
)
def test_activity_rejects_invalid_schedule(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        make_activity(**overrides)


def test_activity_may_end_exactly_at_close_of_day() -> None:
    activity = make_activity(start_min=at(1, 17), duration_slots=2)
    assert activity.duration_min == 60
    assert activity.start_min + activity.duration_min == at(1, 18)
