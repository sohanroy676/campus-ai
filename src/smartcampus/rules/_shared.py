"""Predicates and constants used by both the rule checks and the CP-SAT encodings.

Each rule's meaning is written once here or in its own module; `check` and `post` both call it.
"""

from dataclasses import dataclass
from typing import overload

from ortools.sat.python import cp_model

from smartcampus.domain.entities import Activity, EquipmentPool, Room
from smartcampus.domain.plan import EquipmentMove, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import (
    DAYS,
    MINUTES_PER_DAY,
    SLOTS_PER_WEEK,
    Interval,
    inside_teaching_day,
    minute_to_slot,
    slot_to_minute,
)

SETUP_BUFFER_MIN = 15
MAX_BACK_TO_BACK_TRAVEL_MIN = 10
WEEK_END_MIN = DAYS * MINUTES_PER_DAY


@dataclass(frozen=True)
class Placement:
    """An activity held in a room from `start`. `var` is the CP-SAT literal, None for a constant."""

    activity: Activity
    room: Room
    start: int
    var: cp_model.IntVar | None = None

    @property
    def end(self) -> int:
        return self.start + self.activity.duration_min

    @property
    def slots(self) -> range:
        first = minute_to_slot(self.start)
        return range(first, first + self.activity.duration_slots)


def intervals_overlap(start1: int, end1: int, start2: int, end2: int) -> bool:
    return start1 < end2 and start2 < end1


def valid_starts(problem: RecoveryProblem, activity: Activity) -> list[int]:
    """Slot-aligned starts at which `activity` fits inside the window and one teaching day."""
    window = problem.window
    starts = []
    for slot in range(SLOTS_PER_WEEK):
        minute = slot_to_minute(slot)
        interval = Interval(start=minute, end=minute + activity.duration_min)
        if window.start <= minute and interval.end <= window.end and inside_teaching_day(interval):
            starts.append(minute)
    return starts


def fixed_placements(problem: RecoveryProblem) -> list[Placement]:
    """Activities outside the recovery set stay where they were originally planned."""
    return [
        Placement(a, problem.campus.room(a.room_id), a.start_min)
        for a in problem.activities
        if a.id not in problem.movable_activity_ids
    ]


def plan_placements(problem: RecoveryProblem, plan: Plan) -> list[Placement]:
    """Plan assignments of affected activities in known rooms (R1 reports the rest)."""
    rooms = {r.id for r in problem.campus.rooms}
    return [
        Placement(
            problem.activity(asg.activity_id), problem.campus.room(asg.room_id), asg.start_min
        )
        for asg in plan.assignments
        if asg.activity_id in problem.movable_activity_ids and asg.room_id in rooms
    ]


def placements(problem: RecoveryProblem, plan: Plan) -> list[Placement]:
    return fixed_placements(problem) + plan_placements(problem, plan)


def room_fault_overlaps(problem: RecoveryProblem, room_id: str, start: int, end: int) -> bool:
    return any(
        f.room_id == room_id and intervals_overlap(start, end, f.interval.start, f.interval.end)
        for f in problem.faults
    )


def room_hold_overlaps(problem: RecoveryProblem, room_id: str, start: int, end: int) -> bool:
    return any(
        h.target_kind == "room"
        and h.target_id == room_id
        and intervals_overlap(start, end, h.interval.start, h.interval.end)
        for h in problem.holds
    )


def pool_hold_overlaps(problem: RecoveryProblem, pool_id: str, start: int, end: int) -> bool:
    return any(
        h.target_kind == "equipment"
        and h.target_id == pool_id
        and intervals_overlap(start, end, h.interval.start, h.interval.end)
        for h in problem.holds
    )


def earliest_borrow_start(problem: RecoveryProblem, pool_id: str, class_end: int) -> int | None:
    """Earliest minute a move of `pool_id` may start for a class ending at `class_end`.

    A pool on hold cannot be moved while the hold overlaps the borrow, which runs from the move
    start until the class ends. None means no hold gets in the way.
    """
    return max(
        (
            h.interval.end
            for h in problem.holds
            if h.target_kind == "equipment"
            and h.target_id == pool_id
            and h.interval.start < class_end
        ),
        default=None,
    )


def usable_present_units(
    problem: RecoveryProblem, room_id: str, equipment_type: str, start: int, end: int
) -> int:
    """Units of a type sitting in the room whose pool is not on hold during [start, end)."""
    return sum(
        p.units
        for p in problem.campus.pools
        if p.room_id == room_id
        and p.type == equipment_type
        and not pool_hold_overlaps(problem, p.id, start, end)
    )


def remaining_equipment_need(problem: RecoveryProblem, placement: Placement) -> dict[str, int]:
    """Units per type still missing after the usable units already in the room."""
    need = {}
    for eq_type, required in placement.activity.required_equipment.items():
        present = usable_present_units(
            problem, placement.room.id, eq_type, placement.start, placement.end
        )
        if required > present:
            need[eq_type] = required - present
    return need


def counts_as_moved_in(pool: EquipmentPool, equipment_type: str, room_id: str) -> bool:
    """Units moved from this pool count toward `room_id` only if it is a pool of that type
    that normally sits elsewhere."""
    return pool.type == equipment_type and pool.room_id != room_id


@overload
def move_minutes(pool: EquipmentPool, units: int) -> int: ...


@overload
def move_minutes(pool: EquipmentPool, units: cp_model.IntVar) -> cp_model.LinearExpr: ...


def move_minutes(pool: EquipmentPool, units: int | cp_model.IntVar) -> int | cp_model.LinearExpr:
    """Time one mover needs to carry `units` of `pool` plus the setup buffer.

    Works on plain ints (checks) and on CP-SAT variables (encodings) so the formula lives once.
    """
    return units * pool.move_minutes_per_unit + SETUP_BUFFER_MIN


def known_moves(
    problem: RecoveryProblem, plan: Plan
) -> list[tuple[EquipmentMove, EquipmentPool, Activity]]:
    """Moves whose pool exists and whose activity is an affected one (R4 reports the rest)."""
    pools = {p.id for p in problem.campus.pools}
    return [
        (m, problem.campus.pool(m.pool_id), problem.activity(m.activity_id))
        for m in plan.moves
        if m.pool_id in pools and m.activity_id in problem.movable_activity_ids
    ]
