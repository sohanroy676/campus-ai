import pytest
from builders import asg, at, evolve, make_activity, make_plan, make_problem, move

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
    assert messages(problem, plan) == ["act1 in A1 lacks 1 unit(s) of gpu"]


def test_a_non_movable_pool_never_moves() -> None:
    problem = needing({"rack": 1})
    plan = make_plan(asg("act1", "A2", TUE_10), moves=(move("rack", "act1", 1, at(1, 9), 15),))
    assert messages(problem, plan) == ["pool rack is not movable"]


def test_a_move_cannot_exceed_the_pool() -> None:
    problem = needing({"gpu": 3})
    plan = make_plan(asg("act1", "A2", TUE_10), moves=(move("gpu", "act1", 5, at(1, 8), 40),))
    assert messages(problem, plan) == ["move of 5 units exceeds the 4 in pool gpu"]


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
