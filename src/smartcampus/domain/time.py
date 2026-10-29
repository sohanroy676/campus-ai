"""Slot time model: integer minutes from Monday 00:00, half-open intervals, 30-minute slots."""

from typing import Self

from pydantic import model_validator

from smartcampus.domain.base import FrozenModel

SLOT_MINUTES = 30
MINUTES_PER_DAY = 24 * 60
DAY_START_MIN = 8 * 60
DAY_END_MIN = 18 * 60
SLOTS_PER_DAY = (DAY_END_MIN - DAY_START_MIN) // SLOT_MINUTES
DAYS = 5
SLOTS_PER_WEEK = SLOTS_PER_DAY * DAYS


class Interval(FrozenModel):
    """Half-open interval `[start, end)` in minutes from Monday 00:00."""

    start: int
    end: int

    @model_validator(mode="after")
    def _start_before_end(self) -> Self:
        if self.start < 0 or self.end <= self.start:
            raise ValueError(
                f"interval must satisfy 0 <= start < end, got [{self.start}, {self.end})"
            )
        return self

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, minute: int) -> bool:
        return self.start <= minute < self.end


def day_of(minute: int) -> int:
    return minute // MINUTES_PER_DAY


def day_start(day: int) -> int:
    return day * MINUTES_PER_DAY + DAY_START_MIN


def end_of_teaching_day(day: int) -> int:
    return day * MINUTES_PER_DAY + DAY_END_MIN


def is_slot_aligned(minute: int) -> bool:
    """True if `minute` lies on a slot boundary within the teaching day (end of day included)."""
    in_day = minute % MINUTES_PER_DAY
    return DAY_START_MIN <= in_day <= DAY_END_MIN and (in_day - DAY_START_MIN) % SLOT_MINUTES == 0


def minute_to_slot(minute: int) -> int:
    """Week slot index (0..99) of a slot-aligned start time."""
    day = day_of(minute)
    in_day = minute % MINUTES_PER_DAY
    if not 0 <= day < DAYS or not is_slot_aligned(minute) or in_day == DAY_END_MIN:
        raise ValueError(f"minute {minute} is not the start of a teaching slot")
    return day * SLOTS_PER_DAY + (in_day - DAY_START_MIN) // SLOT_MINUTES


def slot_to_minute(slot: int) -> int:
    if not 0 <= slot < SLOTS_PER_WEEK:
        raise ValueError(f"slot {slot} is outside 0..{SLOTS_PER_WEEK - 1}")
    day, in_day_slot = divmod(slot, SLOTS_PER_DAY)
    return day_start(day) + in_day_slot * SLOT_MINUTES


def inside_teaching_day(interval: Interval) -> bool:
    """True if the interval lies within a single Monday to Friday teaching day."""
    day = day_of(interval.start)
    return (
        0 <= day < DAYS
        and day_start(day) <= interval.start
        and interval.end <= end_of_teaching_day(day)
    )
