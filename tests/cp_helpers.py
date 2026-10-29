"""Fix a plan's values in the CP-SAT variables and ask the solver whether the rules allow it."""

from collections.abc import Iterable

from ortools.sat.python import cp_model

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import WEEK_END_MIN, move_minutes
from smartcampus.rules.base import RuleId
from smartcampus.rules.registry import ALL_RULES, HardRule
from smartcampus.rules.variables import DecisionVars, build_variables


def fix_plan(ctx: DecisionVars, plan: Plan) -> bool:
    """Pin every variable to the plan. False if the variables cannot express the plan at all."""
    problem = ctx.problem
    chosen = {(a.activity_id, a.room_id, a.start_min) for a in plan.assignments}
    if len(chosen) != len(plan.assignments) or not plan.cancelled <= set(ctx.cancelled):
        return False
    known = {
        (aid, o.room.id, o.start): o
        for aid, options in ctx.options.items()
        for o in options
        if o.var is not None
    }
    if not chosen <= set(known):
        return False
    for key, option in known.items():
        assert option.var is not None
        ctx.model.add(option.var == (key in chosen))
    for activity_id, var in ctx.cancelled.items():
        ctx.model.add(var == (activity_id in plan.cancelled))
    seen: set[tuple[str, str]] = set()
    for m in plan.moves:
        key = (m.activity_id, m.pool_id)
        if key not in ctx.units or key in seen:
            return False
        pool = problem.campus.pool(m.pool_id)
        well_formed = (
            m.units <= pool.units
            and 0 <= m.start_min <= WEEK_END_MIN
            and m.end_min - m.start_min == move_minutes(pool, m.units)
        )
        if not well_formed:
            return False
        seen.add(key)
        ctx.model.add(ctx.units[key] == m.units)
        ctx.model.add(ctx.move_start[key] == m.start_min)
    for key, var in ctx.units.items():
        if key not in seen:
            ctx.model.add(var == 0)
    return True


def build_model(problem: RecoveryProblem, rules: Iterable[HardRule]) -> DecisionVars:
    ctx = build_variables(problem)
    for rule in rules:
        rule.post(ctx)
        ctx.model.add(ctx.rule_lit[rule.id] == 1)
    return ctx


def solver() -> cp_model.CpSolver:
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    s.parameters.random_seed = 42
    s.parameters.max_time_in_seconds = 20
    return s


def allows(problem: RecoveryProblem, plan: Plan, rules: Iterable[HardRule] = ALL_RULES) -> bool:
    """True if the model with only `rules` posted accepts exactly this plan."""
    ctx = build_model(problem, rules)
    if not fix_plan(ctx, plan):
        return False
    status = solver().solve(ctx.model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE), status
    return status != cp_model.INFEASIBLE


def conflicting_rules(problem: RecoveryProblem, plan: Plan) -> set[RuleId]:
    """Rules in an infeasible core when every rule sits behind its assumption literal."""
    ctx = build_variables(problem)
    for rule in ALL_RULES:
        rule.post(ctx)
    assert fix_plan(ctx, plan)
    ctx.model.add_assumptions(list(ctx.rule_lit.values()))
    s = solver()
    status = s.solve(ctx.model)
    if status != cp_model.INFEASIBLE:
        return set()
    core = set(s.sufficient_assumptions_for_infeasibility())
    return {rule for rule, lit in ctx.rule_lit.items() if lit.index in core}
