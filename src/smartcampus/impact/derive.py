"""Impact analysis: from faults and holds to the recovery window and the classes that may change.

Rules (docs/model-spec.md section 7, assumptions 21 to 24):
- Only the part of a fault or hold at or after plan time matters, so each is clipped to start no
  earlier than plan time. Otherwise a class that already ended inside the old interval would break
  rule R2 as a fixed class and make the whole input unsolvable.
- The window runs from plan time (or the start of the first affected day, if later) to the end of
  the last affected teaching day.
- Affected: classes that overlap a (clipped) fault or hold on their room, or an equipment hold on
  a pool in their room whose type they need. They must move or be cancelled. A class that is
  already running counts: it must start later or be cancelled.
- Movable: the affected classes, plus classes that have not started, lie inside the window and sit
  in a building within walking distance of a disrupted room (the rule R6 limit of 10 minutes).
"""

from dataclasses import dataclass

from smartcampus.domain.entities import Activity, Fault, SafetyHold
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import (
    DAYS,
    SLOT_MINUTES,
    Interval,
    day_of,
    day_start,
    end_of_teaching_day,
)
from smartcampus.rules._shared import MAX_BACK_TO_BACK_TRAVEL_MIN, intervals_overlap


@dataclass(frozen=True)
class Impact:
    window: Interval
    affected: frozenset[str]
    movable: frozenset[str]
    cohorts: frozenset[str]  # of the movable classes
    faculty: frozenset[str]  # of the movable classes
    faults: tuple[Fault, ...]  # clipped to plan time; those already over are dropped
    holds: tuple[SafetyHold, ...]


def assess(problem: RecoveryProblem) -> Impact:
    plan_time = problem.plan_time_min
    faults = tuple(
        f.model_copy(update={"interval": clipped})
        for f in problem.faults
        if (clipped := _clip(f.interval, plan_time)) is not None
    )
    holds = tuple(
        h.model_copy(update={"interval": clipped})
        for h in problem.holds
        if (clipped := _clip(h.interval, plan_time)) is not None
    )
    window = _window(plan_time, [f.interval for f in faults] + [h.interval for h in holds])
    if window is None:  # nothing left to recover; any valid window will do
        idle = Interval(start=plan_time, end=plan_time + SLOT_MINUTES)
        return Impact(idle, frozenset(), frozenset(), frozenset(), frozenset(), faults, holds)

    campus = problem.campus
    disrupted_rooms: list[tuple[str, Interval]] = [(f.room_id, f.interval) for f in faults]
    disrupted_rooms += [(h.target_id, h.interval) for h in holds if h.target_kind == "room"]
    held_pools = [
        (campus.pool(h.target_id), h.interval) for h in holds if h.target_kind == "equipment"
    ]

    def is_affected(a: Activity) -> bool:
        end = (
            a.start_min + a.duration_min
        )  # intervals start at plan time or later: ended classes miss them
        if any(
            r == a.room_id and intervals_overlap(a.start_min, end, i.start, i.end)
            for r, i in disrupted_rooms
        ):
            return True
        return any(
            p.room_id == a.room_id
            and p.type in a.required_equipment
            and intervals_overlap(a.start_min, end, i.start, i.end)
            for p, i in held_pools
        )

    disrupted_buildings = {campus.room(r).building_id for r, _ in disrupted_rooms}
    disrupted_buildings |= {campus.room(p.room_id).building_id for p, _ in held_pools}

    def is_nearby(a: Activity) -> bool:
        end = a.start_min + a.duration_min
        if a.start_min < max(plan_time, window.start) or end > window.end:
            return False
        building = campus.room(a.room_id).building_id
        return any(
            campus.travel_minutes(building, b) <= MAX_BACK_TO_BACK_TRAVEL_MIN
            for b in disrupted_buildings
        )

    affected = frozenset(a.id for a in problem.activities if is_affected(a))
    movable = affected | {a.id for a in problem.activities if is_nearby(a)}
    chosen = [a for a in problem.activities if a.id in movable]
    return Impact(
        window=window,
        affected=affected,
        movable=frozenset(movable),
        cohorts=frozenset(a.cohort_id for a in chosen),
        faculty=frozenset(f for a in chosen for f in a.faculty_ids),
        faults=faults,
        holds=holds,
    )


def derive_recovery(problem: RecoveryProblem) -> RecoveryProblem:
    """`problem` with its faults and holds clipped to plan time, and window and movable set derived.

    Whatever window and movable ids the input carried are replaced. A second run changes nothing.
    """
    impact = assess(problem)
    return RecoveryProblem.model_validate(
        {
            **dict(problem),
            "faults": impact.faults,
            "holds": impact.holds,
            "window": impact.window,
            "movable_activity_ids": impact.movable,
        }
    )


def _clip(interval: Interval, from_min: int) -> Interval | None:
    """The part of `interval` at or after `from_min`, or None if it is already over."""
    if interval.end <= from_min:
        return None
    return Interval(start=max(interval.start, from_min), end=interval.end)


def _teaching_days(interval: Interval) -> list[int]:
    return [
        day
        for day in range(day_of(interval.start), day_of(interval.end - 1) + 1)
        if 0 <= day < DAYS
        and interval.start < end_of_teaching_day(day)
        and day_start(day) < interval.end
    ]


def _window(plan_time: int, intervals: list[Interval]) -> Interval | None:
    days = [d for i in intervals for d in _teaching_days(i)]
    if not days:
        return None
    return Interval(start=max(plan_time, day_start(min(days))), end=end_of_teaching_day(max(days)))
