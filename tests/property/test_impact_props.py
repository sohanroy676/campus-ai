"""Deriving the recovery never makes a sound timetable unsolvable, and is stable."""

from hypothesis import assume, given, settings
from strategies import problems

from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.impact.derive import assess, derive_recovery
from smartcampus.rules._shared import intervals_overlap
from smartcampus.solver.explain import explain_infeasibility
from smartcampus.solver.solve import InfeasibleInputError, SolverSettings, solve

QUICK = SolverSettings(stage_seconds=(2, 2, 2, 2, 2, 2))


@settings(max_examples=100)
@given(problems())
def test_deriving_twice_changes_nothing(problem: RecoveryProblem) -> None:
    once = derive_recovery(problem)
    assert derive_recovery(once) == once


@settings(max_examples=100)
@given(problems())
def test_the_derived_sets_are_consistent(problem: RecoveryProblem) -> None:
    impact = assess(problem)
    derived = derive_recovery(problem)
    assert impact.affected <= impact.movable <= {a.id for a in problem.activities}
    assert derived.window.start < derived.window.end
    assert derived.movable_activity_ids == impact.movable
    assert all(f.interval.start >= problem.plan_time_min for f in derived.faults)
    assert all(h.interval.start >= problem.plan_time_min for h in derived.holds)
    for activity in problem.activities:
        ended = activity.start_min + activity.duration_min <= problem.plan_time_min
        assert not (ended and activity.id in impact.movable)


@settings(max_examples=100)
@given(problems())
def test_no_fixed_class_is_left_inside_a_disruption(problem: RecoveryProblem) -> None:
    derived = derive_recovery(problem)
    pools = {p.id: p for p in derived.campus.pools}
    for a in derived.activities:
        if a.id in derived.movable_activity_ids:
            continue
        end = a.start_min + a.duration_min
        for f in derived.faults:
            assert not (f.room_id == a.room_id and intervals_overlap(a.start_min, end, *_ends(f)))
        for h in derived.holds:
            if h.target_kind == "room":
                assert not (
                    h.target_id == a.room_id and intervals_overlap(a.start_min, end, *_ends(h))
                )
            else:
                pool = pools[h.target_id]
                needs = pool.room_id == a.room_id and pool.type in a.required_equipment
                assert not (needs and intervals_overlap(a.start_min, end, *_ends(h)))


@settings(max_examples=40)
@given(problems())
def test_a_sound_timetable_stays_solvable_after_any_disruption(problem: RecoveryProblem) -> None:
    sound = RecoveryProblem.model_validate(
        {**dict(problem), "faults": (), "holds": (), "movable_activity_ids": frozenset()}
    )
    assume(explain_infeasibility(sound) == frozenset())  # the original timetable obeys the rules
    try:
        solve(derive_recovery(problem), QUICK)
    except InfeasibleInputError as error:
        raise AssertionError(f"disruption made the input unsolvable: {error}") from error


def _ends(item: Fault | SafetyHold) -> tuple[int, int]:
    return item.interval.start, item.interval.end
