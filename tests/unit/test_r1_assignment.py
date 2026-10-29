from typing import Any

import pytest
from builders import asg, at, evolve, make_activity, make_plan, make_problem

from smartcampus.domain.time import Interval
from smartcampus.rules.r1_assignment import check

TUE_10 = at(1, 10)


def test_one_assignment_or_one_cancellation_is_valid() -> None:
    problem = make_problem()
    assert check(problem, make_plan(asg("act1", "A1", TUE_10))) == []
    assert check(problem, make_plan(cancelled=("act1",))) == []


@pytest.mark.parametrize(
    ("plan", "text"),
    [
        (make_plan(), "neither assigned nor cancelled"),
        (make_plan(asg("act1", "A1", TUE_10), cancelled=("act1",)), "both assigned and cancelled"),
        (make_plan(asg("act1", "A1", TUE_10), asg("act1", "A2", at(1, 12))), "assigned 2 times"),
        (make_plan(asg("act1", "A1", TUE_10), asg("act1", "A1", TUE_10)), "assigned 2 times"),
    ],
)
def test_wrong_number_of_outcomes(plan: Any, text: str) -> None:
    violations = check(make_problem(), plan)
    assert [text in v.message for v in violations] == [True]


def test_unaffected_and_unknown_activities_are_reported() -> None:
    problem = make_problem(
        activities=(make_activity(), make_activity(id="fixed", cohort_id="c2")),
    )
    plan = make_plan(asg("act1", "A1", TUE_10), asg("fixed", "A1", at(1, 14)), cancelled=("ghost",))
    messages = [v.message for v in check(problem, plan)]
    assert sorted(messages) == [
        "activity fixed is not an affected activity",
        "activity ghost is not an affected activity",
    ]


def test_unknown_room_is_reported() -> None:
    violations = check(make_problem(), make_plan(asg("act1", "Z9", TUE_10)))
    assert [v.message for v in violations] == ["unknown room Z9"]


@pytest.mark.parametrize(
    "start",
    [
        at(1, 10, 15),  # not slot-aligned
        at(2, 10),  # a different day, outside the window
        at(1, 7, 30),  # before the teaching day
        at(1, 17, 30),  # two slots would end 18:30
        at(5, 10),  # Saturday
    ],
)
def test_start_must_be_a_slot_inside_window_and_teaching_day(start: int) -> None:
    violations = check(make_problem(), make_plan(asg("act1", "A1", start)))
    assert len(violations) == 1
    assert "cannot start" in violations[0].message


@pytest.mark.parametrize("start", [at(1, 8), at(1, 17)])
def test_first_and_last_fitting_starts_are_valid(start: int) -> None:
    assert check(make_problem(), make_plan(asg("act1", "A1", start))) == []


def test_window_bounds_the_candidate_starts() -> None:
    problem = evolve(make_problem(), window=Interval(start=at(1, 12), end=at(1, 14)))
    assert check(problem, make_plan(asg("act1", "A1", at(1, 11, 30)))) != []
    assert check(problem, make_plan(asg("act1", "A1", at(1, 12)))) == []
    assert check(problem, make_plan(asg("act1", "A1", at(1, 13)))) == []
    assert check(problem, make_plan(asg("act1", "A1", at(1, 13, 30)))) != []


def test_window_starting_off_the_slot_grid_still_has_candidates() -> None:
    problem = evolve(make_problem(), window=Interval(start=at(1, 10, 15), end=at(1, 14)))
    assert check(problem, make_plan(asg("act1", "A1", at(1, 10, 30)))) == []
    assert check(problem, make_plan(asg("act1", "A1", at(1, 10)))) != []
