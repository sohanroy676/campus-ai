"""Hand-built edge cases where the validator check and the CP-SAT encoding must agree.

The property tests compare the two on random plans; these pin the boundaries that random plans
hit only rarely (mover cap, back-to-back travel, holds on moved pools).
"""

from collections.abc import Callable

import pytest
from builders import (
    asg,
    at,
    borrow_scenario,
    evolve,
    make_activity,
    make_campus,
    make_plan,
    make_problem,
    move,
)
from cp_helpers import allows

from smartcampus.domain.entities import SafetyHold
from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.rules.base import RuleId
from smartcampus.rules.registry import RULES_BY_ID

Scenario = tuple[RecoveryProblem, Plan]
TUE_10 = at(1, 10)
GPU_2 = 25  # two gpu units: 2 x 5 + 15 minutes


def three_movers(staff: int, starts: tuple[int, int, int]) -> Scenario:
    problem = make_problem(
        activities=tuple(make_activity(id=f"act{i}") for i in (1, 2, 3)),
        movable_activity_ids=frozenset({"act1", "act2", "act3"}),
        staff_available=staff,
    )
    moves = tuple(move("gpu", f"act{i + 1}", 1, s, 20) for i, s in enumerate(starts))
    return problem, make_plan(cancelled=("act1", "act2", "act3"), moves=moves)


def one_move(start: int) -> Scenario:
    plan = make_plan(asg("act1", "A2", TUE_10), moves=(move("gpu", "act1", 2, start, GPU_2),))
    return make_problem(), plan


def adjacent_classes(walk: int, second_room: str, second_start: int) -> Scenario:
    problem = evolve(
        make_problem(
            activities=(
                make_activity(),
                make_activity(id="act2", faculty_ids=("f2",)),  # same cohort as act1
            ),
            movable_activity_ids=frozenset({"act1", "act2"}),
        ),
        campus=make_campus(walk_ab=walk),
    )
    return problem, make_plan(asg("act1", "A1", TUE_10), asg("act2", second_room, second_start))


def gpu_hold(start: int, end: int) -> Scenario:
    problem = evolve(
        make_problem(activities=(make_activity(required_equipment={"gpu": 3}),)),
        holds=(
            SafetyHold(
                target_kind="equipment", target_id="gpu", interval=Interval(start=start, end=end)
            ),
        ),
    )
    plan = make_plan(asg("act1", "A2", TUE_10), moves=(move("gpu", "act1", 3, at(1, 9), 30),))
    return problem, plan


def unplaced_move() -> Scenario:
    problem, _ = borrow_scenario(2, 1, at(1, 13))
    return problem, make_plan(cancelled=("guest",), moves=(move("gpu", "guest", 2, at(1, 9), 25),))


CASES: list[tuple[RuleId, Callable[[], Scenario], bool]] = [
    # R5: concurrent moves are capped by staff; intervals are half-open
    (RuleId.R5, lambda: three_movers(3, (at(1, 9),) * 3), True),
    (RuleId.R5, lambda: three_movers(2, (at(1, 9),) * 3), False),
    (RuleId.R5, lambda: three_movers(1, (at(1, 9), at(1, 9, 20), at(1, 9, 40))), True),
    (RuleId.R5, lambda: three_movers(1, (at(1, 9), at(1, 9, 19), at(1, 9, 40))), False),
    (RuleId.R5, lambda: three_movers(2, (at(1, 9), at(1, 9, 19), at(1, 9, 40))), True),
    # R5: lead time
    (RuleId.R5, lambda: one_move(TUE_10 - GPU_2), True),
    (RuleId.R5, lambda: one_move(TUE_10 - GPU_2 + 1), False),
    (RuleId.R5, lambda: one_move(at(1, 8)), True),
    (RuleId.R5, lambda: one_move(at(1, 8) - 1), False),
    # R6: back-to-back classes of one cohort in different buildings
    (RuleId.R6, lambda: adjacent_classes(10, "B1", at(1, 11)), True),
    (RuleId.R6, lambda: adjacent_classes(11, "B1", at(1, 11)), False),
    (RuleId.R6, lambda: adjacent_classes(11, "B1", at(1, 9)), False),  # the other order
    (RuleId.R6, lambda: adjacent_classes(11, "A2", at(1, 11)), True),  # same building
    (RuleId.R6, lambda: adjacent_classes(60, "B1", at(1, 11, 30)), True),  # a free slot between
    # R4: units in use at home plus units lent out fit the stock; the return trip counts
    (RuleId.R4, lambda: borrow_scenario(2, 2, at(1, 10)), True),
    (RuleId.R4, lambda: borrow_scenario(3, 2, at(1, 10)), False),
    (RuleId.R4, lambda: borrow_scenario(3, 4, at(1, 11, 30)), True),  # back exactly at 11:30
    (RuleId.R4, lambda: borrow_scenario(3, 4, at(1, 11)), False),
    (RuleId.R4, lambda: borrow_scenario(4, 4, at(1, 13)), True),
    (RuleId.R4, lambda: unplaced_move(), False),
    # R8: a held pool cannot be borrowed from during the hold
    (RuleId.R8, lambda: gpu_hold(at(1, 9, 30), at(1, 9, 45)), False),
    (RuleId.R8, lambda: gpu_hold(at(1, 8), at(1, 9)), True),  # ends as the move starts
    (RuleId.R8, lambda: gpu_hold(at(1, 11), at(1, 12)), True),  # starts as the class ends
    (RuleId.R8, lambda: gpu_hold(at(1, 10, 30), at(1, 10, 45)), False),  # during the class
]


@pytest.mark.parametrize(("rule_id", "build", "expected"), CASES)
def test_check_and_encoding_give_the_same_answer(
    rule_id: RuleId, build: Callable[[], Scenario], expected: bool
) -> None:
    problem, plan = build()
    rule = RULES_BY_ID[rule_id]
    assert (rule.check(problem, plan) == []) is expected
    assert allows(problem, plan, [rule]) is expected
