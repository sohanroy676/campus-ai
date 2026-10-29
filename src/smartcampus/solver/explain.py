"""Name the hard rules that make a problem unsolvable (bad input), via assumption literals."""

from ortools.sat.python import cp_model

from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.base import RuleId
from smartcampus.rules.registry import ALL_RULES
from smartcampus.rules.variables import build_variables


def explain_infeasibility(problem: RecoveryProblem, *, random_seed: int = 42) -> frozenset[RuleId]:
    """Rules in an infeasible core of the model, or an empty set if the model is solvable.

    The core is a sufficient set of rules, not necessarily a minimal one.
    """
    ctx = build_variables(problem)
    for rule in ALL_RULES:
        rule.post(ctx)
    ctx.model.add_assumptions(list(ctx.rule_lit.values()))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = random_seed
    if solver.solve(ctx.model) != cp_model.INFEASIBLE:
        return frozenset()
    core = set(solver.sufficient_assumptions_for_infeasibility())
    return frozenset(rule for rule, lit in ctx.rule_lit.items() if lit.index in core)
