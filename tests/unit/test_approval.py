from builders import asg, at, evolve, make_activity, make_plan, make_problem

from smartcampus.coordinator.approval import Trigger, triggers
from smartcampus.domain.entities import Cohort, SafetyHold
from smartcampus.domain.time import Interval

STAY = asg("act1", "A1", at(1, 10))


def test_an_unchanged_plan_fires_nothing() -> None:
    assert triggers(make_problem(), make_plan(STAY)) == ()


def test_any_cancellation_fires() -> None:
    assert triggers(make_problem(), make_plan(cancelled=("act1",))) == (Trigger.CANCELLATION,)


def test_a_move_to_another_building_fires_and_one_inside_the_building_does_not() -> None:
    problem = make_problem()
    assert triggers(problem, make_plan(asg("act1", "A2", at(1, 10)))) == ()
    assert triggers(problem, make_plan(asg("act1", "B1", at(1, 10)))) == (Trigger.CROSS_BUILDING,)


def test_people_moved_fires_above_100_but_not_at_100() -> None:
    plan = make_plan(asg("act1", "A2", at(1, 12)))  # a changed class counts cohort + faculty
    at_limit = make_problem(cohorts=(Cohort(id="c1", size=99), Cohort(id="c2", size=20)))
    over = make_problem(cohorts=(Cohort(id="c1", size=100), Cohort(id="c2", size=20)))
    assert triggers(at_limit, plan) == ()
    assert triggers(over, plan) == (Trigger.PEOPLE_MOVED,)


def test_a_change_less_than_30_minutes_before_the_original_start_fires() -> None:
    activity = make_activity(start_min=at(1, 8, 30))
    plan = make_plan(asg("act1", "A2", at(1, 9)))
    thirty = make_problem(activities=(activity,), plan_time_min=at(1, 8))
    twenty_nine = make_problem(activities=(activity,), plan_time_min=at(1, 8, 1))
    assert triggers(thirty, plan) == ()
    assert triggers(twenty_nine, plan) == (Trigger.LATE_CHANGE,)


def test_a_late_cancellation_fires_both_triggers() -> None:
    problem = make_problem(activities=(make_activity(start_min=at(1, 8)),))
    assert triggers(problem, make_plan(cancelled=("act1",))) == (
        Trigger.CANCELLATION,
        Trigger.LATE_CHANGE,
    )


def test_a_late_class_that_stays_put_is_not_a_late_change() -> None:
    problem = make_problem(activities=(make_activity(start_min=at(1, 8)),))
    assert triggers(problem, make_plan(asg("act1", "A1", at(1, 8)))) == ()


def test_any_safety_hold_fires() -> None:
    hold = SafetyHold(target_kind="room", target_id="B1", interval=Interval(start=0, end=60))
    assert triggers(evolve(make_problem(), holds=(hold,)), make_plan(STAY)) == (
        Trigger.SAFETY_HOLD,
    )


def test_several_triggers_come_in_a_fixed_order() -> None:
    hold = SafetyHold(target_kind="room", target_id="A2", interval=Interval(start=0, end=60))
    problem = evolve(make_problem(activities=(make_activity(start_min=at(1, 8)),)), holds=(hold,))
    assert triggers(problem, make_plan(asg("act1", "B1", at(1, 9)))) == (
        Trigger.CROSS_BUILDING,
        Trigger.LATE_CHANGE,
        Trigger.SAFETY_HOLD,
    )
