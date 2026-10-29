import pytest
from builders import asg, at, evolve, make_activity, make_campus, make_plan, make_problem

from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.r6_people_conflict import check


def pair(cohort: str = "c2", faculty: tuple[str, ...] = ("f2",), walk: int = 5) -> RecoveryProblem:
    """act1 (c1, f1) and act2 (default c2, f2), both 2 slots; A and B are `walk` minutes apart."""
    return evolve(
        make_problem(
            activities=(
                make_activity(),
                make_activity(id="act2", cohort_id=cohort, faculty_ids=faculty),
            ),
            movable_activity_ids=frozenset({"act1", "act2"}),
        ),
        campus=make_campus(walk_ab=walk),
    )


A1_10 = asg("act1", "A1", at(1, 10))  # 10:00-11:00 in building A


def test_different_people_may_overlap() -> None:
    assert check(pair(), make_plan(A1_10, asg("act2", "A2", at(1, 10)))) == []


@pytest.mark.parametrize(
    ("cohort", "faculty"),
    [("c1", ("f2",)), ("c2", ("f1",)), ("c2", ("f2", "f1"))],
)
def test_sharing_a_cohort_or_a_teacher_forbids_overlap(
    cohort: str, faculty: tuple[str, ...]
) -> None:
    plan = make_plan(A1_10, asg("act2", "A2", at(1, 10, 30)))
    [violation] = check(pair(cohort, faculty), plan)
    assert violation.activity_ids == ("act1", "act2")
    assert "overlap" in violation.message


def test_same_building_back_to_back_is_fine() -> None:
    plan = make_plan(A1_10, asg("act2", "A2", at(1, 11)))
    assert check(pair("c1", walk=60), plan) == []


@pytest.mark.parametrize(("walk", "violations"), [(0, 0), (10, 0), (11, 1), (25, 1)])
def test_back_to_back_across_buildings_needs_a_short_walk(walk: int, violations: int) -> None:
    plan = make_plan(A1_10, asg("act2", "B1", at(1, 11)))
    assert len(check(pair("c1", walk=walk), plan)) == violations


def test_back_to_back_is_checked_in_both_orders() -> None:
    plan = make_plan(A1_10, asg("act2", "B1", at(1, 9)))  # act2 ends at 10:00 as act1 starts
    assert len(check(pair("c1", walk=11), plan)) == 1


def test_one_free_slot_between_far_buildings_is_fine() -> None:
    plan = make_plan(A1_10, asg("act2", "B1", at(1, 11, 30)))
    assert check(pair("c1", walk=60), plan) == []


def test_unrelated_people_may_be_back_to_back_anywhere() -> None:
    plan = make_plan(A1_10, asg("act2", "B1", at(1, 11)))
    assert check(pair(walk=60), plan) == []


def test_cancelled_activity_cannot_conflict() -> None:
    plan = make_plan(A1_10, cancelled=("act2",))
    assert check(pair("c1"), plan) == []


def test_fixed_activity_conflicts_with_a_moved_one() -> None:
    problem = evolve(pair("c1"), movable_activity_ids=frozenset({"act1"}))
    # act2 stays at its original Tue 10:00 in A1; moving act1 on top of it, same cohort
    plan = make_plan(asg("act1", "A2", at(1, 10, 30)))
    assert len(check(problem, plan)) == 1
