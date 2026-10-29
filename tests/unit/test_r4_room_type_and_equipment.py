import pytest
from builders import (
    asg,
    at,
    borrow_scenario,
    evolve,
    make_activity,
    make_plan,
    make_problem,
    move,
)

from smartcampus.domain.entities import SafetyHold
from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.rules.r4_room_type_and_equipment import check

TUE_10 = at(1, 10)


def needing(equipment: dict[str, int], **overrides: object) -> RecoveryProblem:
    return make_problem(activities=(make_activity(required_equipment=equipment, **overrides),))


def messages(problem: RecoveryProblem, plan: Plan) -> list[str]:
    return [v.message for v in check(problem, plan)]


def test_room_type_must_be_allowed() -> None:
    problem = make_problem(activities=(make_activity(allowed_room_types=frozenset({"lab"})),))
    assert check(problem, make_plan(asg("act1", "A1", TUE_10))) == []
    [violation] = check(problem, make_plan(asg("act1", "A2", TUE_10)))
    assert "not allowed" in violation.message


def test_equipment_already_in_the_room_is_enough() -> None:
    problem = needing({"gpu": 4})
    assert check(problem, make_plan(asg("act1", "A1", TUE_10))) == []


def test_equipment_missing_without_a_move() -> None:
    problem = needing({"gpu": 3})
    assert messages(problem, make_plan(asg("act1", "A2", TUE_10))) == [
        "act1 in A2 lacks 3 unit(s) of gpu"
    ]


@pytest.mark.parametrize(("moved", "lacking"), [(3, 0), (4, 0), (2, 1), (1, 2)])
def test_moved_units_make_up_the_difference(moved: int, lacking: int) -> None:
    problem = needing({"gpu": 3})
    plan = make_plan(
        asg("act1", "A2", TUE_10), moves=(move("gpu", "act1", moved, at(1, 9), 5 * moved + 15),)
    )
    found = messages(problem, plan)
    assert len(found) == (1 if lacking else 0)
    if lacking:
        assert f"lacks {lacking} unit(s)" in found[0]


def test_units_moved_from_the_destination_room_do_not_count_twice() -> None:
    problem = needing({"gpu": 5})  # room A1 holds only 4
    plan = make_plan(asg("act1", "A1", TUE_10), moves=(move("gpu", "act1", 1, at(1, 9), 20),))
    # the lent unit is also taken from the stock the class itself uses: 4 at home + 1 lent > 4
    assert messages(problem, plan) == [
        "act1 in A1 lacks 1 unit(s) of gpu",
        f"gpu in A1: 5 unit(s) in use or lent out at minute {TUE_10}, only 4 in stock",
    ]


def test_a_non_movable_pool_never_moves() -> None:
    problem = needing({"rack": 1})
    plan = make_plan(asg("act1", "A2", TUE_10), moves=(move("rack", "act1", 1, at(1, 9), 15),))
    assert messages(problem, plan) == ["pool rack is not movable"]


def test_a_move_cannot_exceed_the_pool() -> None:
    problem = needing({"gpu": 3})
    plan = make_plan(asg("act1", "A2", TUE_10), moves=(move("gpu", "act1", 5, at(1, 8), 40),))
    assert messages(problem, plan) == [
        "move of 5 units exceeds the 4 in pool gpu",
        f"gpu in A1: 5 unit(s) in use or lent out at minute {at(1, 8)}, only 4 in stock",
    ]


def test_move_structure_errors() -> None:
    problem = make_problem(
        activities=(make_activity(), make_activity(id="fixed", cohort_id="c2", room_id="A2"))
    )
    plan = make_plan(
        asg("act1", "A1", TUE_10),
        moves=(
            move("nope", "act1", 1, at(1, 9), 20),
            move("gpu", "fixed", 1, at(1, 9), 20),
            move("gpu", "act1", 1, at(1, 9), 20),
            move("gpu", "act1", 2, at(1, 8), 25),
        ),
    )
    assert sorted(messages(problem, plan)) == [
        "2 moves of pool gpu for act1; at most one is allowed",
        "move for unaffected activity fixed",
        "move of unknown pool nope",
    ]


def test_pool_on_hold_during_the_class_does_not_count_as_present() -> None:
    problem = evolve(
        needing({"gpu": 3}),
        holds=(
            SafetyHold(
                target_kind="equipment",
                target_id="gpu",
                interval=Interval(start=at(1, 10, 30), end=at(1, 12)),
            ),
        ),
    )
    assert messages(problem, make_plan(asg("act1", "A1", TUE_10))) == [
        "act1 in A1 lacks 3 unit(s) of gpu"
    ]


def test_hold_ending_when_the_class_starts_is_harmless() -> None:
    problem = evolve(
        needing({"gpu": 3}),
        holds=(
            SafetyHold(
                target_kind="equipment",
                target_id="gpu",
                interval=Interval(start=at(1, 8), end=TUE_10),
            ),
        ),
    )
    assert check(problem, make_plan(asg("act1", "A1", TUE_10))) == []


def stock_messages(problem: RecoveryProblem, plan: Plan) -> list[str]:
    return [m for m in messages(problem, plan) if "in stock" in m]


def test_home_use_plus_lent_units_may_exactly_fill_the_stock() -> None:
    problem, plan = borrow_scenario(units=2, home_need=2, home_start=TUE_10)
    assert messages(problem, plan) == []


def test_one_unit_over_the_stock_is_a_violation() -> None:
    problem, plan = borrow_scenario(units=3, home_need=2, home_start=TUE_10)
    assert stock_messages(problem, plan) == [
        f"gpu in A1: 5 unit(s) in use or lent out at minute {TUE_10}, only 4 in stock"
    ]


def test_units_are_back_exactly_when_the_return_trip_ends() -> None:
    # class ends 11:00, 3 gpus take 5 x 3 + 15 = 30 minutes to return: back at 11:30 (half-open)
    problem, plan = borrow_scenario(units=3, home_need=4, home_start=at(1, 11, 30))
    assert stock_messages(problem, plan) == []
    problem, plan = borrow_scenario(units=3, home_need=4, home_start=at(1, 11))
    assert len(stock_messages(problem, plan)) == 1


def test_a_lend_that_ends_before_the_home_class_starts_does_not_clash() -> None:
    problem, plan = borrow_scenario(units=4, home_need=4, home_start=at(1, 13))
    assert stock_messages(problem, plan) == []


def test_a_move_needs_a_placed_class() -> None:
    problem, _ = borrow_scenario(units=2, home_need=1, home_start=at(1, 13))
    plan = make_plan(cancelled=("guest",), moves=(move("gpu", "guest", 2, at(1, 9), 25),))
    assert messages(problem, plan) == [
        "move of gpu for guest needs exactly one placed class, found 0 end time(s)"
    ]


def test_a_move_for_a_class_placed_twice_at_different_times_is_ambiguous() -> None:
    problem, _ = borrow_scenario(units=2, home_need=1, home_start=at(1, 13))
    plan = make_plan(
        asg("guest", "A2", at(1, 10)),
        asg("guest", "A2", at(1, 12)),
        moves=(move("gpu", "guest", 2, at(1, 9), 25),),
    )
    assert any("found 2 end time(s)" in m for m in messages(problem, plan))


def test_two_borrowers_share_one_stock() -> None:
    problem = make_problem(
        activities=(
            make_activity(id="g1", required_equipment={"gpu": 2}),
            make_activity(
                id="g2", cohort_id="c2", faculty_ids=("f2",), required_equipment={"gpu": 2}
            ),
        ),
        movable_activity_ids=frozenset({"g1", "g2"}),
    )
    both = make_plan(
        asg("g1", "A2", TUE_10),
        asg("g2", "B1", TUE_10),
        moves=(move("gpu", "g1", 2, at(1, 9), 25), move("gpu", "g2", 3, at(1, 9), 30)),
    )
    assert len(stock_messages(problem, both)) == 1  # 2 + 3 lent out of 4
    fewer = make_plan(
        asg("g1", "A2", TUE_10),
        asg("g2", "B1", TUE_10),
        moves=(move("gpu", "g1", 2, at(1, 9), 25), move("gpu", "g2", 2, at(1, 9), 25)),
    )
    assert stock_messages(problem, fewer) == []
