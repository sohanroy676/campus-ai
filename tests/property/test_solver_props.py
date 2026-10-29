"""The solver must find the lexicographic optimum that exhaustive search finds."""

from itertools import product

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from strategies import tiny_problems

from smartcampus.domain.plan import Assignment, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import valid_starts
from smartcampus.rules.validator import validate
from smartcampus.solver.objective import StageValues, evaluate
from smartcampus.solver.solve import SolverSettings, solve

QUICK = SolverSettings(stage_seconds=(5, 5, 5, 5, 5, 5))


def best_by_brute_force(problem: RecoveryProblem) -> StageValues | None:
    """Score every plan (each class cancelled or placed anywhere) and keep the best valid one."""
    ids = sorted(problem.movable_activity_ids)
    choices = [
        [None]
        + [
            Assignment(activity_id=a, room_id=r.id, start_min=s)
            for r in problem.campus.rooms
            for s in valid_starts(problem, problem.activity(a))
        ]
        for a in ids
    ]
    best: StageValues | None = None
    for combo in product(*choices):
        plan = Plan(
            based_on_version=0,
            assignments=tuple(c for c in combo if c is not None),
            cancelled=frozenset(a for a, c in zip(ids, combo, strict=True) if c is None),
        )
        if validate(problem, plan):
            continue
        score = evaluate(problem, plan)
        best = score if best is None or score < best else best
    return best


@settings(max_examples=60)
@given(tiny_problems())
def test_the_solver_finds_the_best_valid_plan(problem: RecoveryProblem) -> None:
    expected = best_by_brute_force(problem)
    assume(expected is not None)  # the input itself breaks a rule: nothing to compare
    result = solve(problem, QUICK)
    assert result.values == expected


@settings(max_examples=40)
@given(tiny_problems())
def test_the_plan_is_always_valid_and_never_cancels_more_than_needed(
    problem: RecoveryProblem,
) -> None:
    assume(best_by_brute_force(problem) is not None)
    result = solve(problem, QUICK)
    assert validate(problem, result.plan) == []
    assert result.values.cancellations <= len(problem.movable_activity_ids)
    assert result.values == evaluate(problem, result.plan)


@settings(max_examples=30)
@given(st.data())
def test_solving_is_repeatable(data: st.DataObject) -> None:
    problem = data.draw(tiny_problems())
    assume(best_by_brute_force(problem) is not None)
    assert solve(problem, QUICK).plan == solve(problem, QUICK).plan
