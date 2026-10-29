from typing import Any

from builders import asg, at, evolve, make_activity, make_plan, make_problem

from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.rules.r2_room_conflict import check


def two_activities(**overrides: Any) -> RecoveryProblem:
    return make_problem(
        activities=(make_activity(), make_activity(id="act2", cohort_id="c2", faculty_ids=("f2",))),
        movable_activity_ids=frozenset({"act1", "act2"}),
        **overrides,
    )


def test_distinct_rooms_and_touching_intervals_are_fine() -> None:
    problem = two_activities()
    different_rooms = make_plan(asg("act1", "A1", at(1, 10)), asg("act2", "A2", at(1, 10)))
    back_to_back = make_plan(asg("act1", "A1", at(1, 10)), asg("act2", "A1", at(1, 11)))
    assert check(problem, different_rooms) == []
    assert check(problem, back_to_back) == []  # [10:00, 11:00) and [11:00, 12:00) do not overlap


def test_one_slot_of_overlap_is_a_conflict() -> None:
    problem = two_activities()
    plan = make_plan(asg("act1", "A1", at(1, 10)), asg("act2", "A1", at(1, 10, 30)))
    [violation] = check(problem, plan)
    assert violation.activity_ids == ("act1", "act2")
    assert violation.room_ids == ("A1",)


def test_movable_activity_conflicts_with_a_fixed_one() -> None:
    problem = make_problem(
        activities=(make_activity(), make_activity(id="fixed", cohort_id="c2", room_id="A2")),
    )
    plan = make_plan(asg("act1", "A2", at(1, 10, 30)))
    assert len(check(problem, plan)) == 1
    assert check(problem, make_plan(asg("act1", "A2", at(1, 11)))) == []


def test_fault_closes_the_room_but_half_open_end_reopens_it() -> None:
    fault = Fault(
        id="f", room_id="A1", kind="ac", interval=Interval(start=at(1, 10), end=at(1, 12))
    )
    problem = evolve(make_problem(), faults=(fault,))
    assert len(check(problem, make_plan(asg("act1", "A1", at(1, 11))))) == 1
    assert len(check(problem, make_plan(asg("act1", "A1", at(1, 9, 30))))) == 1
    assert check(problem, make_plan(asg("act1", "A1", at(1, 9)))) == []  # ends as the fault starts
    assert check(problem, make_plan(asg("act1", "A1", at(1, 12)))) == []
    assert check(problem, make_plan(asg("act1", "A2", at(1, 11)))) == []


def test_room_hold_also_closes_the_room() -> None:
    hold = SafetyHold(
        target_kind="room", target_id="A2", interval=Interval(start=at(1, 9), end=at(1, 11))
    )
    problem = evolve(make_problem(), holds=(hold,))
    assert len(check(problem, make_plan(asg("act1", "A2", at(1, 10))))) == 1
    assert check(problem, make_plan(asg("act1", "A2", at(1, 11)))) == []


def test_equipment_hold_does_not_close_a_room() -> None:
    hold = SafetyHold(
        target_kind="equipment", target_id="gpu", interval=Interval(start=at(1, 9), end=at(1, 18))
    )
    problem = evolve(make_problem(), holds=(hold,))
    assert check(problem, make_plan(asg("act1", "A1", at(1, 10)))) == []


def test_cancelled_activities_hold_no_room() -> None:
    assert check(two_activities(), make_plan(cancelled=("act1", "act2"))) == []
