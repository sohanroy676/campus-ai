import pytest
from builders import at
from pydantic import ValidationError

from smartcampus.domain.time import (
    DAY_END_MIN,
    DAY_START_MIN,
    SLOTS_PER_DAY,
    SLOTS_PER_WEEK,
    Interval,
    day_of,
    end_of_teaching_day,
    inside_teaching_day,
    is_slot_aligned,
    minute_to_slot,
    slot_to_minute,
)


def test_constants_match_spec() -> None:
    assert (DAY_START_MIN, DAY_END_MIN) == (480, 1080)
    assert SLOTS_PER_DAY == 20
    assert SLOTS_PER_WEEK == 100


def test_slot_round_trip_for_every_slot() -> None:
    for slot in range(SLOTS_PER_WEEK):
        assert minute_to_slot(slot_to_minute(slot)) == slot


def test_first_and_last_slot() -> None:
    assert slot_to_minute(0) == at(0, 8)
    assert slot_to_minute(99) == at(4, 17, 30)
    assert slot_to_minute(20) == at(1, 8)


@pytest.mark.parametrize("slot", [-1, 100])
def test_slot_to_minute_rejects_out_of_range(slot: int) -> None:
    with pytest.raises(ValueError, match="outside"):
        slot_to_minute(slot)


@pytest.mark.parametrize(
    "minute",
    [
        at(0, 7, 30),  # before the day
        at(0, 8, 15),  # unaligned
        at(0, 18),  # end of day is a boundary, not a slot start
        at(5, 8),  # Saturday
        -30,
    ],
)
def test_minute_to_slot_rejects_non_slot_starts(minute: int) -> None:
    with pytest.raises(ValueError, match="not the start"):
        minute_to_slot(minute)


def test_alignment_includes_end_of_day_boundary() -> None:
    assert is_slot_aligned(at(2, 18))
    assert not is_slot_aligned(at(2, 18, 30))
    assert not is_slot_aligned(at(2, 12, 29))


def test_interval_is_half_open() -> None:
    a = Interval(start=600, end=660)
    b = Interval(start=660, end=720)
    assert not a.overlaps(b)
    assert not b.overlaps(a)
    assert a.overlaps(Interval(start=659, end=700))
    assert a.contains(600)
    assert not a.contains(660)


@pytest.mark.parametrize(("start", "end"), [(10, 10), (20, 10), (-1, 5)])
def test_interval_rejects_empty_or_negative(start: int, end: int) -> None:
    with pytest.raises(ValidationError):
        Interval(start=start, end=end)


def test_inside_teaching_day_boundaries() -> None:
    assert inside_teaching_day(Interval(start=at(0, 8), end=at(0, 18)))
    assert not inside_teaching_day(Interval(start=at(0, 17), end=at(0, 18, 30)))
    assert not inside_teaching_day(Interval(start=at(0, 7, 30), end=at(0, 9)))
    assert not inside_teaching_day(Interval(start=at(0, 17), end=at(1, 9)))
    assert not inside_teaching_day(Interval(start=at(5, 9), end=at(5, 10)))


def test_day_helpers() -> None:
    assert day_of(at(3, 9)) == 3
    assert end_of_teaching_day(2) == at(2, 18)
