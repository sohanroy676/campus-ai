from typing import Any

import pytest
from builders import asg, at, evolve, make_activity, make_plan, make_problem, move

from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import WEEK_END_MIN
from smartcampus.rules.r5_move_lead_time import check

TUE_10 = at(1, 10)
PLACED = asg("act1", "A2", TUE_10)  # class runs 10:00-11:00; plan time is Tue 08:00
TWO_GPUS = 2 * 5 + 15  # units x 5 min + 15 min setup


def one_move(start: int, minutes: int = TWO_GPUS, units: int = 2) -> Any:
    return make_plan(PLACED, moves=(move("gpu", "act1", units, start, minutes),))


def texts(plan: Any, problem: RecoveryProblem | None = None) -> list[str]:
    return [v.message for v in check(problem or make_problem(), plan)]


def test_move_finishing_well_before_class_is_valid() -> None:
    assert texts(one_move(at(1, 9))) == []


def test_move_finishing_exactly_when_class_starts_is_valid() -> None:
    assert texts(one_move(TUE_10 - TWO_GPUS)) == []


def test_move_finishing_a_minute_late_is_not() -> None:
    assert texts(one_move(TUE_10 - TWO_GPUS + 1)) == [
        "move of gpu for act1 finishes after the class starts"
    ]


def test_move_may_start_exactly_at_plan_time_but_not_before() -> None:
    assert texts(one_move(at(1, 8))) == []
    assert texts(one_move(at(1, 8) - 1)) == ["move of gpu for act1 starts before plan time"]


@pytest.mark.parametrize("minutes", [TWO_GPUS - 1, TWO_GPUS + 1])
def test_planned_length_must_equal_units_times_minutes_plus_setup(minutes: int) -> None:
    [text] = texts(one_move(at(1, 9), minutes=minutes))
    assert text == f"move of gpu for act1 takes {TWO_GPUS} minutes, not planned length"


def test_move_cannot_run_past_the_end_of_the_week() -> None:
    plan = make_plan(PLACED, moves=(move("gpu", "act1", 1, WEEK_END_MIN - 10, 20),))
    assert "move of gpu for act1 ends after the week" in texts(plan)


def test_zero_minute_pool_still_costs_the_setup_buffer() -> None:
    campus = make_problem().campus
    cheap = campus.pools[0].model_copy(update={"move_minutes_per_unit": 0})
    problem = evolve(make_problem(), campus=evolve(campus, pools=(cheap, campus.pools[1])))
    assert texts(make_plan(PLACED, moves=(move("gpu", "act1", 3, at(1, 9), 15),)), problem) == []
    assert texts(make_plan(PLACED, moves=(move("gpu", "act1", 3, at(1, 9), 14),)), problem) != []


def test_move_for_a_cancelled_activity_only_needs_timing_rules() -> None:
    plan = make_plan(cancelled=("act1",), moves=(move("gpu", "act1", 2, TUE_10 + 600, TWO_GPUS),))
    assert texts(plan) == []


def three_activities(staff: int) -> RecoveryProblem:
    return make_problem(
        activities=tuple(make_activity(id=f"act{i}") for i in (1, 2, 3)),
        movable_activity_ids=frozenset({"act1", "act2", "act3"}),
        staff_available=staff,
    )


def moves_for_three(starts: tuple[int, int, int]) -> Any:
    return make_plan(
        cancelled=("act1", "act2", "act3"),
        moves=tuple(move("gpu", f"act{i + 1}", 1, s, 20) for i, s in enumerate(starts)),
    )


def test_concurrent_moves_are_capped_by_staff() -> None:
    same_time = moves_for_three((at(1, 9),) * 3)
    assert texts(same_time, three_activities(staff=3)) == []
    [text] = texts(same_time, three_activities(staff=2))
    assert text == f"3 moves run at minute {at(1, 9)}, only 2 movers available"


def test_back_to_back_moves_share_a_mover() -> None:
    # [9:00, 9:20), [9:20, 9:40), [9:40, 10:00): one mover is enough because intervals are half-open
    plan = moves_for_three((at(1, 9), at(1, 9, 20), at(1, 9, 40)))
    assert texts(plan, three_activities(staff=1)) == []


def test_one_minute_of_overlap_needs_a_second_mover() -> None:
    plan = moves_for_three((at(1, 9), at(1, 9, 19), at(1, 9, 40)))
    assert len(texts(plan, three_activities(staff=1))) == 1
    assert texts(plan, three_activities(staff=2)) == []
