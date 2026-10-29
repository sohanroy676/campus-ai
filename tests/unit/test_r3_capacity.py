import pytest
from builders import asg, at, evolve, make_plan, make_problem

from smartcampus.domain.entities import Cohort
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.r3_capacity import check


def problem_with_cohort_size(size: int) -> RecoveryProblem:
    return evolve(make_problem(), cohorts=(Cohort(id="c1", size=size), Cohort(id="c2", size=20)))


@pytest.mark.parametrize(("size", "violations"), [(29, 0), (30, 0), (31, 1)])
def test_capacity_boundary_in_a_30_seat_room(size: int, violations: int) -> None:
    plan = make_plan(asg("act1", "A1", at(1, 10)))
    assert len(check(problem_with_cohort_size(size), plan)) == violations


def test_violation_names_activity_and_room() -> None:
    [violation] = check(problem_with_cohort_size(45), make_plan(asg("act1", "B1", at(1, 10))))
    assert (violation.activity_ids, violation.room_ids) == (("act1",), ("B1",))
    assert check(problem_with_cohort_size(45), make_plan(asg("act1", "A2", at(1, 10)))) == []


def test_cancelled_activity_needs_no_seats() -> None:
    assert check(problem_with_cohort_size(500), make_plan(cancelled=("act1",))) == []
