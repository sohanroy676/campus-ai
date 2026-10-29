"""Seeded synthetic scenarios: a campus, a conflict-free week of classes, and one disruption.

The same (size, load, severity, seed) always gives the same problem. The baseline timetable is
built so that it obeys the room, capacity, accessibility, equipment and people rules; the
disruption is then placed over a class that is running, and `impact/` derives the window and the
movable classes. Randomness comes from one `random.Random(seed)` and every choice iterates over
sorted or ordered lists, so the output does not depend on hash order.
"""

import random
from dataclasses import dataclass
from typing import Final

from smartcampus.domain.entities import (
    Activity,
    Building,
    Campus,
    Cohort,
    EquipmentPool,
    Faculty,
    Fault,
    Room,
    SafetyHold,
    Walk,
)
from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import Provenance, RecoveryProblem
from smartcampus.domain.time import (
    DAYS,
    MINUTES_PER_DAY,
    SLOT_MINUTES,
    SLOTS_PER_DAY,
    SLOTS_PER_WEEK,
    Interval,
    end_of_teaching_day,
    slot_to_minute,
)
from smartcampus.impact.derive import derive_recovery
from smartcampus.rules._shared import MAX_BACK_TO_BACK_TRAVEL_MIN
from smartcampus.rules.validator import validate

GENERATOR_VERSION: Final = "1"

SIZES: Final = ("small", "medium", "large")
LOADS: Final = (50, 75, 90)
SEVERITIES: Final = ("room", "building", "hold")

PLAN_LEAD_MIN = 120  # the disruption is known two hours before it starts
MAX_BUILD_TRIES = 10
FAULT_KINDS = ("ac_failure", "flooding", "power_outage")
GPU_UNITS = 4
GPU_MOVE_MINUTES = 5


class GeneratorError(ValueError):
    """The parameters are not valid, or no valid scenario could be built from the seed."""


@dataclass(frozen=True)
class SizeSpec:
    buildings: int
    rooms_per_building: int


_SIZE_SPECS: Final = {
    "small": SizeSpec(buildings=2, rooms_per_building=4),
    "medium": SizeSpec(buildings=3, rooms_per_building=7),
    "large": SizeSpec(buildings=5, rooms_per_building=8),
}


def generate_scenario(size: str, load: int, severity: str, seed: int) -> RecoveryProblem:
    """A seeded recovery problem. Raises `GeneratorError` for unknown parameters."""
    if size not in _SIZE_SPECS:
        raise GeneratorError(f"size must be one of {', '.join(SIZES)}, got {size!r}")
    if not 10 <= load <= 95:
        raise GeneratorError(f"load must be a percentage from 10 to 95, got {load}")
    if severity not in SEVERITIES:
        raise GeneratorError(f"severity must be one of {', '.join(SEVERITIES)}, got {severity!r}")
    rng = random.Random(f"{GENERATOR_VERSION}/{size}/{load}/{severity}/{seed}")
    provenance = Provenance(
        generator_version=GENERATOR_VERSION, seed=seed, size=size, load=load, severity=severity
    )
    for _ in range(MAX_BUILD_TRIES):
        problem = _build(rng, _SIZE_SPECS[size], load, severity, provenance)
        if problem is not None:
            return problem
    raise GeneratorError(f"no valid scenario for {size}/{load}/{severity}/seed {seed}")


def _build(
    rng: random.Random, spec: SizeSpec, load: int, severity: str, provenance: Provenance
) -> RecoveryProblem | None:
    campus = _campus(rng, spec)
    n_rooms = len(campus.rooms)
    cohorts = tuple(
        Cohort(
            id=f"coh-{i + 1:03d}",
            size=rng.randint(12, 30),
            step_free_required=rng.random() < 0.1,
        )
        for i in range(2 * n_rooms)
    )
    faculty = tuple(Faculty(id=f"fac-{i + 1:03d}") for i in range(2 * n_rooms))
    activities = _timetable(rng, campus, cohorts, faculty, load)
    if not activities:
        return None
    faults, holds, plan_time = _disruption(rng, campus, activities, severity)
    draft = RecoveryProblem(
        campus=campus,
        cohorts=cohorts,
        faculty=faculty,
        activities=activities,
        faults=faults,
        holds=holds,
        movable_activity_ids=frozenset(),
        window=Interval(start=plan_time, end=plan_time + SLOT_MINUTES),
        plan_time_min=plan_time,
        provenance=provenance,
    )
    problem = derive_recovery(draft)
    # Cancelling every movable class is the plan that always exists unless the fixed classes
    # already break a rule, so an empty violation list means the scenario is solvable.
    everything_cancelled = Plan(
        based_on_version=0, assignments=(), cancelled=problem.movable_activity_ids, moves=()
    )
    if validate(problem, everything_cancelled):
        return None
    return problem


def _campus(rng: random.Random, spec: SizeSpec) -> Campus:
    buildings = tuple(Building(id=f"B{b + 1}") for b in range(spec.buildings))
    rooms: list[Room] = []
    for building in buildings:
        for i in range(spec.rooms_per_building):
            is_lab = i % 2 == 1
            rooms.append(
                Room(
                    id=f"{building.id}-{'lab' if is_lab else 'lec'}-{i // 2 + 1:02d}",
                    building_id=building.id,
                    type="lab" if is_lab else "lecture",
                    capacity=rng.choice((30, 40)) if is_lab else rng.choice((40, 60, 80)),
                    step_free=rng.random() < 0.8,
                )
            )
    # Every building keeps one step-free room of each type, so step-free cohorts can be placed.
    rooms = [
        r.model_copy(update={"step_free": True}) if _is_first_of_type(r, rooms) else r
        for r in rooms
    ]
    pools = tuple(
        EquipmentPool(
            id=f"gpu-{room.id}",
            type="gpu",
            room_id=room.id,
            units=GPU_UNITS,
            movable=True,
            move_minutes_per_unit=GPU_MOVE_MINUTES,
        )
        for room in rooms
        if room.type == "lab" and (room.id.endswith("-01") or rng.random() < 0.4)
    )
    walks = tuple(
        Walk(a=a.id, b=b.id, minutes=rng.randint(3, 15))
        for i, a in enumerate(buildings)
        for b in buildings[i + 1 :]
    )
    return Campus(buildings=buildings, rooms=tuple(rooms), pools=pools, walks=walks)


def _is_first_of_type(room: Room, rooms: list[Room]) -> bool:
    return (
        next(r for r in rooms if r.building_id == room.building_id and r.type == room.type) == room
    )


def _timetable(
    rng: random.Random,
    campus: Campus,
    cohorts: tuple[Cohort, ...],
    faculty: tuple[Faculty, ...],
    load: int,
) -> tuple[Activity, ...]:
    """Random classes placed one at a time until the target share of room-slots is used."""
    target = round(len(campus.rooms) * SLOTS_PER_WEEK * load / 100)
    room_busy: dict[str, set[int]] = {r.id: set() for r in campus.rooms}
    people_busy: dict[str, dict[int, str]] = {}  # person id -> slot -> building id
    gpu_rooms = {p.room_id for p in campus.pools if p.type == "gpu"}
    placed: list[tuple[int, str, Activity]] = []
    used = 0
    for _ in range(40 * target):
        if used >= target:
            break
        cohort = rng.choice(cohorts)
        lab = rng.random() < 0.4
        slots = rng.choice((2, 3, 4)) if lab else rng.choice((2, 2, 3))
        people = [cohort.id, *[f.id for f in _pick_faculty(rng, faculty)]]
        rooms = [
            r
            for r in campus.rooms
            if r.type == ("lab" if lab else "lecture")
            and r.capacity >= cohort.size
            and (r.step_free or not cohort.step_free_required)
        ]
        if not rooms:
            continue
        room = rng.choice(rooms)
        first = rng.randrange(SLOTS_PER_DAY - slots + 1)
        start_slot = rng.randrange(DAYS) * SLOTS_PER_DAY + first
        span = range(start_slot, start_slot + slots)
        if room_busy[room.id].intersection(span):
            continue
        if not all(_person_free(people_busy, p, span, room.building_id, campus) for p in people):
            continue
        equipment = {"gpu": rng.randint(1, GPU_UNITS)} if lab and room.id in gpu_rooms else {}
        if equipment and rng.random() < 0.5:
            equipment = {}
        room_busy[room.id].update(span)
        for person in people:
            people_busy.setdefault(person, {}).update({s: room.building_id for s in span})
        used += slots
        placed.append(
            (
                start_slot,
                room.id,
                Activity(
                    id="",
                    cohort_id=cohort.id,
                    faculty_ids=tuple(people[1:]),
                    duration_slots=slots,
                    allowed_room_types=frozenset({room.type}),
                    required_equipment=equipment,
                    room_id=room.id,
                    start_min=slot_to_minute(start_slot),
                ),
            )
        )
    placed.sort(key=lambda item: (item[0], item[1]))
    return tuple(
        a.model_copy(update={"id": f"act-{i + 1:04d}"}) for i, (_, _, a) in enumerate(placed)
    )


def _pick_faculty(rng: random.Random, faculty: tuple[Faculty, ...]) -> list[Faculty]:
    return rng.sample(list(faculty), 2 if rng.random() < 0.2 else 1)


def _person_free(
    busy: dict[str, dict[int, str]],
    person: str,
    span: range,
    building: str,
    campus: Campus,
) -> bool:
    """Free for the whole span, and no back-to-back class in a building too far away (R6)."""
    slots = busy.get(person, {})
    if any(s in slots for s in span):
        return False
    for neighbour in (span.start - 1, span.stop):
        same_day = neighbour // SLOTS_PER_DAY == span.start // SLOTS_PER_DAY
        other = slots.get(neighbour)
        if (
            same_day
            and other is not None
            and campus.travel_minutes(other, building) > MAX_BACK_TO_BACK_TRAVEL_MIN
        ):
            return False
    return True


def _disruption(
    rng: random.Random, campus: Campus, activities: tuple[Activity, ...], severity: str
) -> tuple[tuple[Fault, ...], tuple[SafetyHold, ...], int]:
    """A fault or hold that starts when a chosen class does. Returns (faults, holds, plan time)."""
    target = rng.choice(activities)
    day = target.start_min // MINUTES_PER_DAY
    length = rng.choice((4, 6, 8)) * SLOT_MINUTES
    interval = Interval(
        start=target.start_min, end=min(target.start_min + length, end_of_teaching_day(day))
    )
    plan_time = max(0, interval.start - PLAN_LEAD_MIN)
    room = campus.room(target.room_id)
    if severity == "hold":
        pool = next(
            (
                p
                for p in campus.pools
                if p.room_id == room.id and p.type in target.required_equipment
            ),
            None,
        )
        if pool is not None:
            return (
                (),
                (SafetyHold(target_kind="equipment", target_id=pool.id, interval=interval),),
                plan_time,
            )
        return (
            (),
            (SafetyHold(target_kind="room", target_id=room.id, interval=interval),),
            plan_time,
        )
    kind = rng.choice(FAULT_KINDS)
    if severity == "building":
        faulted = [r for r in campus.rooms if r.building_id == room.building_id]
    else:
        faulted = [room]
    faults = tuple(
        Fault(id=f"fault-{i + 1:02d}", room_id=r.id, kind=kind, interval=interval)
        for i, r in enumerate(faulted)
    )
    return faults, (), plan_time
