"""Small hand-built campus and problem used by unit tests."""

from typing import Any

from smartcampus.domain.entities import (
    Activity,
    Building,
    Campus,
    Cohort,
    EquipmentPool,
    Faculty,
    Room,
    Walk,
)
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import MINUTES_PER_DAY, Interval


def at(day: int, hour: int, minute: int = 0) -> int:
    """Minutes from Monday 00:00 (day 0 is Monday)."""
    return day * MINUTES_PER_DAY + hour * 60 + minute


def make_campus(walk_ab: int = 5) -> Campus:
    return Campus(
        buildings=(Building(id="A"), Building(id="B")),
        rooms=(
            Room(id="A1", building_id="A", type="lab", capacity=30, step_free=True),
            Room(id="A2", building_id="A", type="lecture", capacity=60, step_free=True),
            Room(id="B1", building_id="B", type="lecture", capacity=40, step_free=False),
        ),
        pools=(
            EquipmentPool(
                id="gpu", type="gpu", room_id="A1", units=4, movable=True, move_minutes_per_unit=5
            ),
            EquipmentPool(
                id="rack",
                type="rack",
                room_id="A1",
                units=2,
                movable=False,
                move_minutes_per_unit=0,
            ),
        ),
        walks=(Walk(a="A", b="B", minutes=walk_ab),),
    )


def make_activity(**overrides: Any) -> Activity:
    fields: dict[str, Any] = {
        "id": "act1",
        "cohort_id": "c1",
        "faculty_ids": ("f1",),
        "duration_slots": 2,
        "allowed_room_types": frozenset({"lab", "lecture"}),
        "required_equipment": {},
        "room_id": "A1",
        "start_min": at(1, 10),
    }
    fields.update(overrides)
    return Activity(**fields)


def make_problem(**overrides: Any) -> RecoveryProblem:
    """One activity (Tue 10:00-11:00 in A1), plan made Tue 08:00, window Tue 08:00-18:00."""
    fields: dict[str, Any] = {
        "campus": make_campus(),
        "cohorts": (Cohort(id="c1", size=25), Cohort(id="c2", size=20)),
        "faculty": (Faculty(id="f1"), Faculty(id="f2")),
        "activities": (make_activity(),),
        "movable_activity_ids": frozenset({"act1"}),
        "window": Interval(start=at(1, 8), end=at(1, 18)),
        "plan_time_min": at(1, 8),
    }
    fields.update(overrides)
    return RecoveryProblem(**fields)
