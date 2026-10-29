from typing import Any

import pytest
from builders import at, evolve, make_activity, make_campus, make_problem

from smartcampus.domain.entities import Activity, Cohort, Faculty, Fault, SafetyHold
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.impact.derive import assess, derive_recovery
from smartcampus.solver.solve import SolverSettings, solve

TUE_DAY = Interval(start=at(1, 8), end=at(1, 18))


def span(start: int, end: int, day: int = 1) -> Interval:
    return Interval(start=at(day, start), end=at(day, end))


def fault(room: str, interval: Interval, fault_id: str = "f1") -> Fault:
    return Fault(id=fault_id, room_id=room, kind="ac", interval=interval)


def problem_with(
    *activities: Activity,
    faults: tuple[Fault, ...] = (),
    holds: tuple[SafetyHold, ...] = (),
    **kw: object,
) -> RecoveryProblem:
    """The base problem with these activities (all registered as movable placeholders)."""
    fields: dict[str, object] = {"faults": faults, "holds": holds}
    if activities:
        cohort_ids = sorted({a.cohort_id for a in activities})
        faculty_ids = sorted({f for a in activities for f in a.faculty_ids})
        fields |= {
            "activities": activities,
            "movable_activity_ids": frozenset(a.id for a in activities),
            "cohorts": tuple(Cohort(id=c, size=20) for c in cohort_ids),
            "faculty": tuple(Faculty(id=f) for f in faculty_ids),
        }
    return evolve(make_problem(), **fields, **kw)


def act(
    activity_id: str, room: str, start_h: int, start_m: int = 0, slots: int = 2, **kw: Any
) -> Activity:
    return make_activity(
        id=activity_id,
        cohort_id=f"c-{activity_id}",
        faculty_ids=(f"f-{activity_id}",),
        room_id=room,
        start_min=at(1, start_h, start_m),
        duration_slots=slots,
        **kw,
    )


def test_without_disruptions_nothing_is_affected_and_the_window_is_idle() -> None:
    impact = assess(make_problem())
    assert impact.affected == impact.movable == frozenset()
    assert impact.window == Interval(start=at(1, 8), end=at(1, 8, 30))


def test_a_fault_over_a_class_affects_it_and_opens_the_rest_of_the_day() -> None:
    problem = problem_with(faults=(fault("A1", span(10, 12)),))
    impact = assess(problem)
    assert impact.affected == impact.movable == {"act1"}
    assert impact.window == TUE_DAY


def test_a_fault_that_only_touches_the_class_boundary_does_not_affect_it() -> None:
    # act1 runs 10:00-11:00; the fault starts exactly when it ends. Intervals are half-open.
    impact = assess(problem_with(faults=(fault("A1", span(11, 12)),)))
    assert impact.affected == frozenset()
    assert impact.movable == {"act1"}  # still nearby: same building


def test_a_class_in_another_room_is_not_affected_by_the_fault() -> None:
    other = act("other", "A2", 10)
    impact = assess(problem_with(act("act1", "A1", 14), other, faults=(fault("A1", span(10, 12)),)))
    assert impact.affected == frozenset()
    assert impact.movable == {"act1", "other"}


@pytest.mark.parametrize(("walk", "nearby"), [(5, True), (10, True), (11, False)])
def test_nearby_means_a_walk_of_at_most_ten_minutes(walk: int, nearby: bool) -> None:
    far = act("far", "B1", 14)
    problem = problem_with(
        act("act1", "A1", 10),
        far,
        faults=(fault("A1", span(10, 12)),),
        campus=make_campus(walk_ab=walk),
    )
    impact = assess(problem)
    assert impact.affected == {"act1"}
    assert ("far" in impact.movable) is nearby


def test_a_class_that_ended_before_plan_time_is_left_alone() -> None:
    # 08:00-09:00 in A1 while the fault runs 08:00-12:00, but the plan is made at 10:00.
    problem = problem_with(
        act("done", "A1", 8), faults=(fault("A1", span(8, 12)),), plan_time_min=at(1, 10)
    )
    impact = assess(problem)
    assert impact.affected == impact.movable == frozenset()
    assert impact.faults[0].interval == span(10, 12)  # clipped to plan time
    assert impact.window == span(10, 18)


def test_clipping_keeps_a_finished_class_from_breaking_the_rules() -> None:
    problem = problem_with(
        act("done", "A1", 8), faults=(fault("A1", span(8, 12)),), plan_time_min=at(1, 10)
    )
    plan = solve(derive_recovery(problem), SolverSettings(stage_seconds=(1,) * 6)).plan
    assert plan.assignments == () and plan.cancelled == frozenset()


def test_a_class_already_running_is_affected_and_may_start_before_the_window() -> None:
    running = act("running", "A1", 9, 30)  # 09:30-10:30
    impact = assess(
        problem_with(running, faults=(fault("A1", span(10, 12)),), plan_time_min=at(1, 10))
    )
    assert impact.affected == impact.movable == {"running"}
    assert impact.window.start == at(1, 10)


def test_a_class_that_has_started_is_not_pulled_in_just_for_being_nearby() -> None:
    started = act("started", "A2", 9)  # 09:00-10:00, plan made 09:30
    impact = assess(
        problem_with(
            act("act1", "A1", 10),
            started,
            faults=(fault("A1", span(10, 12)),),
            plan_time_min=at(1, 9, 30),
        )
    )
    assert impact.affected == {"act1"}
    assert impact.movable == {"act1"}


def test_classes_on_other_days_are_outside_the_window() -> None:
    monday = make_activity(id="mon", cohort_id="c1", room_id="A2", start_min=at(0, 10))
    wednesday = make_activity(id="wed", cohort_id="c1", room_id="A2", start_min=at(2, 10))
    problem = problem_with(
        act("act1", "A1", 10), monday, wednesday, faults=(fault("A1", span(10, 12)),)
    )
    assert assess(problem).movable == {"act1"}  # the window is Tuesday only


def test_an_equipment_hold_affects_only_classes_that_need_that_equipment_in_that_room() -> None:
    hold = SafetyHold(target_kind="equipment", target_id="gpu", interval=span(9, 11))
    needs = act("needs", "A1", 10, required_equipment={"gpu": 2})
    plain = act("plain", "A1", 10)
    elsewhere = act("elsewhere", "A2", 10, required_equipment={"gpu": 1})
    wrong_type = act("rack", "A1", 10, required_equipment={"rack": 1})
    impact = assess(problem_with(needs, plain, elsewhere, wrong_type, holds=(hold,)))
    assert impact.affected == {"needs"}
    assert impact.movable == {"needs", "plain", "elsewhere", "rack"}  # all in building A


def test_a_room_hold_affects_like_a_fault() -> None:
    hold = SafetyHold(target_kind="room", target_id="A1", interval=span(10, 11))
    assert assess(problem_with(holds=(hold,))).affected == {"act1"}


def test_the_window_spans_every_affected_teaching_day() -> None:
    long_fault = fault("A1", Interval(start=at(0, 14), end=at(2, 10)))
    impact = assess(problem_with(faults=(long_fault,), plan_time_min=at(0, 9)))
    assert impact.window == Interval(start=at(0, 9), end=at(2, 18))


def test_the_window_starts_at_the_day_start_when_plan_time_is_earlier() -> None:
    impact = assess(problem_with(faults=(fault("A1", span(10, 12)),), plan_time_min=at(0, 9)))
    assert impact.window == TUE_DAY


def test_a_weekend_fault_changes_nothing() -> None:
    weekend = fault("A1", Interval(start=at(5, 10), end=at(5, 12)))
    impact = assess(problem_with(faults=(weekend,)))
    assert impact.movable == frozenset() and impact.window.end == at(1, 8, 30)


def test_a_fault_over_before_plan_time_is_dropped() -> None:
    impact = assess(problem_with(faults=(fault("A1", span(8, 9)),), plan_time_min=at(1, 10)))
    assert impact.faults == () and impact.movable == frozenset()


def test_cohorts_and_faculty_are_those_of_the_movable_classes() -> None:
    problem = problem_with(
        act("a", "A1", 10), act("b", "B1", 14), faults=(fault("A1", span(10, 12)),)
    )
    impact = assess(problem)
    assert impact.movable == {"a", "b"}  # b is in building B, 5 minutes away
    assert impact.cohorts == {f"c-{i}" for i in impact.movable}
    assert impact.faculty == {f"f-{i}" for i in impact.movable}


def test_deriving_replaces_any_window_and_movable_ids_it_was_given() -> None:
    problem = problem_with(
        faults=(fault("A1", span(10, 12)),),
        window=span(10, 11),
        movable_activity_ids=frozenset(),
    )
    derived = derive_recovery(problem)
    assert derived.window == TUE_DAY and derived.movable_activity_ids == {"act1"}
    assert derived.activities == problem.activities


def test_deriving_twice_changes_nothing() -> None:
    once = derive_recovery(
        problem_with(act("a", "A1", 8), faults=(fault("A1", span(8, 12)),), plan_time_min=at(1, 10))
    )
    assert derive_recovery(once) == once
