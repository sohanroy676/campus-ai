"""Greedy always gives a valid plan, never beats the solver, and fails only on bad input."""

from hypothesis import given, settings
from strategies import tiny_problems

from smartcampus.baselines.greedy import greedy
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.validator import validate
from smartcampus.solver.objective import evaluate
from smartcampus.solver.solve import InfeasibleInputError, SolverSettings, solve

QUICK = SolverSettings(stage_seconds=(5, 5, 5, 5, 5, 5))


@settings(max_examples=60)
@given(tiny_problems())
def test_greedy_is_valid_and_no_better_than_the_solver(problem: RecoveryProblem) -> None:
    try:
        optimum = solve(problem, QUICK).values
    except InfeasibleInputError as bad_input:
        try:
            greedy(problem)
        except InfeasibleInputError as error:
            assert error.rules == bad_input.rules
            return
        raise AssertionError("greedy planned for input the solver calls infeasible") from None
    plan = greedy(problem)
    assert validate(problem, plan) == []
    assert evaluate(problem, plan) >= optimum
