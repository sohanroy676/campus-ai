from typing import Literal

from builders import asg, at, evolve, make_activity, make_plan, make_problem, move

from smartcampus.domain.entities import SafetyHold
from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.rules.r8_safety_hold import check

TUE_10 = at(1, 10)  # act1 runs 10:00-11:00


def held(kind: Literal["room", "equipment"], target: str, start: int, end: int) -> SafetyHold:
    return SafetyHold(target_kind=kind, target_id=target, interval=Interval(start=start, end=end))


def with_holds(*holds: SafetyHold) -> RecoveryProblem:
    return evolve(
        make_problem(activities=(make_activity(required_equipment={"gpu": 3}),)), holds=holds
    )


def gpu_move_to_a2(start: int, minutes: int = 30) -> Plan:
    return make_plan(asg("act1", "A2", TUE_10), moves=(move("gpu", "act1", 3, start, minutes),))


def test_room_on_hold_cannot_host_during_the_hold() -> None:
    problem = with_holds(held("room", "A2", at(1, 10, 30), at(1, 12)))
    [violation] = check(problem, make_plan(asg("act1", "A2", TUE_10)))
    assert violation.room_ids == ("A2",)


def test_hold_boundaries_are_half_open() -> None:
    ends_as_class_starts = with_holds(held("room", "A2", at(1, 8), TUE_10))
    starts_as_class_ends = with_holds(held("room", "A2", at(1, 11), at(1, 12)))
    plan = make_plan(asg("act1", "A2", TUE_10))
    assert check(ends_as_class_starts, plan) == []
    assert check(starts_as_class_ends, plan) == []


def test_hold_on_another_room_is_irrelevant() -> None:
    assert (
        check(
            with_holds(held("room", "B1", at(1, 8), at(1, 18))),
            make_plan(asg("act1", "A2", TUE_10)),
        )
        == []
    )


def test_pool_on_hold_cannot_be_moved_while_the_hold_overlaps_the_borrow() -> None:
    problem = with_holds(held("equipment", "gpu", at(1, 9, 30), at(1, 9, 45)))
    [violation] = check(problem, gpu_move_to_a2(at(1, 9)))
    assert "pool gpu is on safety hold" in violation.message


def test_hold_during_the_class_after_the_move_still_blocks_the_borrow() -> None:
    problem = with_holds(held("equipment", "gpu", at(1, 10, 30), at(1, 10, 45)))
    assert len(check(problem, gpu_move_to_a2(at(1, 9)))) == 1


def test_pool_hold_boundaries_are_half_open() -> None:
    ends_when_move_starts = with_holds(held("equipment", "gpu", at(1, 8), at(1, 9)))
    starts_when_class_ends = with_holds(held("equipment", "gpu", at(1, 11), at(1, 12)))
    assert check(ends_when_move_starts, gpu_move_to_a2(at(1, 9))) == []
    assert check(starts_when_class_ends, gpu_move_to_a2(at(1, 9))) == []


def test_pool_hold_is_irrelevant_when_nothing_moves() -> None:
    problem = with_holds(held("equipment", "gpu", at(1, 8), at(1, 18)))
    assert check(problem, make_plan(asg("act1", "A1", TUE_10))) == []


def test_cancelled_activity_with_a_held_pool_is_fine() -> None:
    problem = with_holds(held("equipment", "gpu", at(1, 8), at(1, 18)))
    plan = make_plan(cancelled=("act1",), moves=(move("gpu", "act1", 3, at(1, 9), 30),))
    assert check(problem, plan) == []
