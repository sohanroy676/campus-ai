import pytest
from builders import asg, at, evolve, make_plan, make_problem

from smartcampus.domain.entities import Cohort
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.r7_accessibility import check


def problem_with_step_free(required: bool) -> RecoveryProblem:
    cohorts = (Cohort(id="c1", size=25, step_free_required=required), Cohort(id="c2", size=20))
    return evolve(make_problem(), cohorts=cohorts)


@pytest.mark.parametrize(
    ("required", "room", "violations"),
    [
        (True, "A1", 0),
        (True, "B1", 1),  # B1 has steps
        (False, "B1", 0),
        (False, "A1", 0),
    ],
)
def test_step_free_only_binds_cohorts_that_need_it(
    required: bool, room: str, violations: int
) -> None:
    plan = make_plan(asg("act1", room, at(1, 10)))
    assert len(check(problem_with_step_free(required), plan)) == violations


def test_cancelled_activity_needs_no_step_free_room() -> None:
    assert check(problem_with_step_free(True), make_plan(cancelled=("act1",))) == []
