"""Campus entities: buildings, rooms, equipment, cohorts, faculty, activities, faults, holds."""

from functools import cached_property
from typing import Literal, Self

from pydantic import Field, model_validator

from smartcampus.domain.base import FrozenModel
from smartcampus.domain.time import (
    SLOT_MINUTES,
    Interval,
    inside_teaching_day,
    is_slot_aligned,
)


def _require_unique(kind: str, ids: list[str]) -> None:
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {kind} ids")


class Building(FrozenModel):
    id: str


class Walk(FrozenModel):
    """Walking time between two distinct buildings, symmetric."""

    a: str
    b: str
    minutes: int = Field(ge=0)


class Room(FrozenModel):
    id: str
    building_id: str
    type: str
    capacity: int = Field(gt=0)
    step_free: bool


class EquipmentPool(FrozenModel):
    """Units of one equipment type that normally sit in one room."""

    id: str
    type: str
    room_id: str
    units: int = Field(gt=0)
    movable: bool
    move_minutes_per_unit: int = Field(ge=0)


class Campus(FrozenModel):
    buildings: tuple[Building, ...]
    rooms: tuple[Room, ...]
    pools: tuple[EquipmentPool, ...] = ()
    walks: tuple[Walk, ...] = ()

    @model_validator(mode="after")
    def _check_references(self) -> Self:
        building_ids = [b.id for b in self.buildings]
        _require_unique("building", building_ids)
        _require_unique("room", [r.id for r in self.rooms])
        _require_unique("equipment pool", [p.id for p in self.pools])
        known_buildings = set(building_ids)
        room_ids = {r.id for r in self.rooms}
        for room in self.rooms:
            if room.building_id not in known_buildings:
                raise ValueError(f"room {room.id} is in unknown building {room.building_id}")
        for pool in self.pools:
            if pool.room_id not in room_ids:
                raise ValueError(f"pool {pool.id} is in unknown room {pool.room_id}")
        pairs = [frozenset((w.a, w.b)) for w in self.walks]
        if any(len(p) != 2 or not p <= known_buildings for p in pairs):
            raise ValueError("walks must join two distinct, known buildings")
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate walk between the same two buildings")
        if len(pairs) != len(building_ids) * (len(building_ids) - 1) // 2:
            raise ValueError("walks must give a time for every pair of distinct buildings")
        return self

    @cached_property
    def _rooms_by_id(self) -> dict[str, Room]:
        return {r.id: r for r in self.rooms}

    @cached_property
    def _pools_by_id(self) -> dict[str, EquipmentPool]:
        return {p.id: p for p in self.pools}

    @cached_property
    def _walk_minutes(self) -> dict[frozenset[str], int]:
        return {frozenset((w.a, w.b)): w.minutes for w in self.walks}

    def room(self, room_id: str) -> Room:
        return self._rooms_by_id[room_id]

    def pool(self, pool_id: str) -> EquipmentPool:
        return self._pools_by_id[pool_id]

    def travel_minutes(self, b1: str, b2: str) -> int:
        """Symmetric walking time; zero within one building."""
        if b1 == b2:
            return 0
        return self._walk_minutes[frozenset((b1, b2))]


class Cohort(FrozenModel):
    id: str
    size: int = Field(gt=0)
    step_free_required: bool = False


class Faculty(FrozenModel):
    id: str


class Activity(FrozenModel):
    """A class session. `room_id` and `start_min` are the originally planned assignment."""

    id: str
    cohort_id: str
    faculty_ids: tuple[str, ...]
    duration_slots: int = Field(gt=0)
    allowed_room_types: frozenset[str] = Field(min_length=1)
    required_equipment: dict[str, int] = Field(default_factory=dict)
    room_id: str
    start_min: int

    @model_validator(mode="after")
    def _check_schedule(self) -> Self:
        if len(self.faculty_ids) != len(set(self.faculty_ids)):
            raise ValueError(f"activity {self.id} lists a faculty member twice")
        if any(n <= 0 for n in self.required_equipment.values()):
            raise ValueError(f"activity {self.id} requires a non-positive equipment count")
        if not is_slot_aligned(self.start_min) or not inside_teaching_day(
            Interval(start=self.start_min, end=self.start_min + self.duration_slots * SLOT_MINUTES)
        ):
            raise ValueError(f"activity {self.id} is not slot-aligned inside a teaching day")
        return self

    @property
    def duration_min(self) -> int:
        return self.duration_slots * SLOT_MINUTES


class Fault(FrozenModel):
    id: str
    room_id: str
    kind: str
    interval: Interval


class SafetyHold(FrozenModel):
    """A room or equipment pool that is unusable for the whole interval."""

    target_kind: Literal["room", "equipment"]
    target_id: str
    interval: Interval
