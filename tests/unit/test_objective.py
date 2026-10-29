from dataclasses import astuple

import pytest
from builders import asg, at, evolve, make_activity, make_plan, make_problem, move

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.solver.objective import StageValues, evaluate, room_rank

TUE_10 = at(1, 10)


def values(problem: RecoveryProblem, plan: Plan) -> tuple[int, ...]:
    return astuple(evaluate(problem, plan))


def placed(room: str, start: int = TUE_10) -> Plan:
    return make_plan(asg("act1", room, start))


# base problem: act1 = cohort c1 (25 students) + 1 teacher = 26 people, originally A1 Tue
# 10:00-11:00, plan made Tue 08:00; rooms sort A1, A2, B1; A1 and A2 are in building A, B1 in B.


def test_unchanged_plan_costs_nothing() -> None:
    assert values(make_problem(), placed("A1")) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    ("room", "start", "expected"),
    [
        ("A2", TUE_10, (0, 26, 0, 0, 1)),  # other room, same building: rank of A2 is 1
        ("B1", TUE_10, (0, 26, 0, 0, 1002)),  # other building: 1000 + rank of B1 (2)
        ("A1", at(1, 10, 30), (0, 26, 30, 0, 0)),  # 30 minutes later, same room rank 0
        ("A1", at(1, 12), (0, 26, 120, 0, 0)),  # delay is counted in minutes
        ("A1", at(1, 9, 30), (0, 26, 0, 0, 0)),  # earlier is a change but never a delay
        ("B1", at(1, 11), (0, 26, 60, 0, 1002)),
    ],
)
def test_one_changed_class(room: str, start: int, expected: tuple[int, ...]) -> None:
    assert values(make_problem(), placed(room, start)) == expected


def test_cancelling_counts_only_in_the_first_stage() -> None:
    assert values(make_problem(), make_plan(cancelled=("act1",))) == (1, 0, 0, 0, 0)


@pytest.mark.parametrize(
    ("plan_time", "people"),
    [
        (at(1, 9, 29), 26),  # 31 minutes before the start
        (at(1, 9, 30), 26),  # exactly 30 minutes: not "less than 30"
        (at(1, 9, 31), 52),  # 29 minutes before the start
        (TUE_10, 52),
        (at(1, 11), 52),  # the class has already started
    ],
)
def test_lateness_factor_boundary(plan_time: int, people: int) -> None:
    problem = evolve(make_problem(), plan_time_min=plan_time)
    assert evaluate(problem, placed("A2")).people_moved == people


def two_classes_of_one_cohort(prior: int) -> RecoveryProblem:
    return evolve(
        make_problem(
            activities=(
                make_activity(),
                make_activity(id="act2", faculty_ids=("f2",), room_id="A2", start_min=at(1, 12)),
            ),
            movable_activity_ids=frozenset({"act1", "act2"}),
        ),
        prior_moves_this_week={"c1": prior} if prior else {},
    )


@pytest.mark.parametrize(
    ("prior", "moved_classes", "people"),
    [
        (0, 1, 26),  # first move this week: no surcharge
        (0, 2, 52 + 50),  # second move in the same plan: one surcharge
        (1, 1, 26 + 50),  # already moved earlier this week
        (1, 2, 52 + 100),
    ],
)
def test_repeat_move_surcharge(prior: int, moved_classes: int, people: int) -> None:
    problem = two_classes_of_one_cohort(prior)
    first = asg("act1", "A2", TUE_10)
    second = asg("act2", "A1", at(1, 12)) if moved_classes == 2 else asg("act2", "A2", at(1, 12))
    assert evaluate(problem, make_plan(first, second)).people_moved == people


def test_cohorts_are_counted_separately() -> None:
    problem = make_problem(
        activities=(make_activity(), make_activity(id="act2", cohort_id="c2", faculty_ids=("f2",))),
        movable_activity_ids=frozenset({"act1", "act2"}),
    )
    plan = make_plan(asg("act1", "A2", TUE_10), asg("act2", "B1", TUE_10))
    assert evaluate(problem, plan).people_moved == 26 + 21  # no surcharge across cohorts


def test_unaffected_classes_contribute_nothing() -> None:
    problem = make_problem(
        activities=(make_activity(), make_activity(id="fixed", cohort_id="c2", room_id="B1")),
    )
    assert values(problem, placed("A2")) == (0, 26, 0, 0, 1)


def moved_plan(room: str, units: int = 2) -> Plan:
    return make_plan(
        asg("act1", room, TUE_10), moves=(move("gpu", "act1", units, at(1, 9), 5 * units + 15),)
    )


@pytest.mark.parametrize(
    ("room", "units", "cost"),
    [
        ("A2", 2, 25),  # 2 x 5 + 15 staff-minutes, pool and room both in building A
        ("A2", 4, 35),
        ("B1", 2, 25 + 20),  # pool in building A, class lands in building B
    ],
)
def test_equipment_cost(room: str, units: int, cost: int) -> None:
    assert evaluate(make_problem(), moved_plan(room, units)).cost == cost


def test_a_move_for_a_cancelled_class_still_costs_minutes() -> None:
    plan = make_plan(cancelled=("act1",), moves=(move("gpu", "act1", 2, at(1, 9), 25),))
    assert values(make_problem(), plan) == (1, 0, 0, 25, 0)


def test_room_rank_uses_alphabetical_order_not_listing_order() -> None:
    problem = make_problem()
    reordered = evolve(
        problem, campus=evolve(problem.campus, rooms=tuple(reversed(problem.campus.rooms)))
    )
    assert [room_rank(reordered, r) for r in ("A1", "A2", "B1")] == [0, 1, 2]
    assert values(reordered, placed("A2")) == values(problem, placed("A2"))


def test_stage_values_compare_lexicographically() -> None:
    assert StageValues(0, 999, 999, 999, 999) < StageValues(1, 0, 0, 0, 0)
    assert StageValues(1, 5, 0, 0, 0) < StageValues(1, 6, 0, 0, 0)
    assert min([StageValues(2, 0, 0, 0, 0), StageValues(1, 9, 9, 9, 9)]) == StageValues(
        1, 9, 9, 9, 9
    )
