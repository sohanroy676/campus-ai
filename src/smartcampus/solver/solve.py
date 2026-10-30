"""Solve a recovery problem: one CP-SAT model, six lexicographic stages (C, P, D, K, S, T).

After each stage its optimum is fixed as a constraint ("stage value <= optimum") before the next
stage runs. A stage that hits its time limit keeps the best solution it found.
"""

from dataclasses import dataclass
from enum import StrEnum

from ortools.sat.python import cp_model

from smartcampus.domain.plan import Assignment, EquipmentMove, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import move_minutes
from smartcampus.rules.base import RuleId
from smartcampus.rules.registry import ALL_RULES
from smartcampus.rules.validator import assert_valid
from smartcampus.rules.variables import DecisionVars, build_variables
from smartcampus.solver.explain import explain_infeasibility
from smartcampus.solver.objective import StageValues, evaluate, stage_expression

STAGE_NAMES = ("cancellations", "people_moved", "delay", "cost", "start_shift", "tie_break")


@dataclass(frozen=True)
class SolverSettings:
    """Defaults from the spec: 30 s split 10 / 10 / 3 / 3 / 2 / 2, single worker, fixed seed."""

    stage_seconds: tuple[float, float, float, float, float, float] = (10, 10, 3, 3, 2, 2)
    num_workers: int = 1
    random_seed: int = 42


class StageStatus(StrEnum):
    OPTIMAL = "optimal"
    TIME_LIMIT = "time_limit"  # the best solution found within the limit, not proven optimal


@dataclass(frozen=True)
class StageReport:
    name: str
    value: int
    status: StageStatus
    seconds: float


@dataclass(frozen=True)
class SolveResult:
    plan: Plan
    values: StageValues
    stages: tuple[StageReport, ...]


class InfeasibleInputError(Exception):
    """No plan exists, not even cancelling everything: the input already breaks hard rules."""

    def __init__(self, rules: frozenset[RuleId]) -> None:
        self.rules = rules
        names = ", ".join(sorted(rule.value for rule in rules)) or "unknown"
        super().__init__(f"the problem has no solution; conflicting rules: {names}")


class NoSolutionError(Exception):
    """The solver found no solution within the first stage's time limit."""


def solve(
    problem: RecoveryProblem,
    settings: SolverSettings | None = None,
    *,
    based_on_version: int = 0,
    hint: Plan | None = None,
) -> SolveResult:
    """`hint` is a plan to start the search from; without one it starts from cancel-everything."""
    settings = settings or SolverSettings()
    ctx = build_variables(problem)
    for rule in ALL_RULES:
        rule.post(ctx)
        ctx.model.add(ctx.rule_lit[rule.id] == 1)
    if hint is None:
        _hint_cancel_everything(ctx)
    else:
        _hint_plan(ctx, hint)

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = settings.num_workers
    solver.parameters.random_seed = settings.random_seed
    reports: list[StageReport] = []
    best: Plan | None = None
    for index, (name, seconds) in enumerate(zip(STAGE_NAMES, settings.stage_seconds, strict=True)):
        expression = stage_expression(ctx, index)  # its helper variables join the model only now
        ctx.model.minimize(expression)
        solver.parameters.max_time_in_seconds = seconds
        status = solver.solve(ctx.model)
        if status == cp_model.INFEASIBLE:
            # Cancelling everything is always allowed, so this can only be bad input.
            raise InfeasibleInputError(
                explain_infeasibility(problem, random_seed=settings.random_seed)
            )
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if best is None:
                raise NoSolutionError(f"no solution found within {seconds} s")
            reports.append(StageReport(name, reports[-1].value, StageStatus.TIME_LIMIT, seconds))
            continue
        value = round(solver.objective_value)
        ctx.model.add(expression <= value)
        best = _extract_plan(ctx, solver, based_on_version)
        _hint_solution(ctx, solver)
        stage_status = StageStatus.OPTIMAL if status == cp_model.OPTIMAL else StageStatus.TIME_LIMIT
        reports.append(StageReport(name, value, stage_status, solver.wall_time))
    assert best is not None
    assert_valid(problem, best)  # the validator re-checks every plan with the same rules
    return SolveResult(best, evaluate(problem, best), tuple(reports))


def _all_variables(ctx: DecisionVars) -> list[cp_model.IntVar]:
    variables = [o.var for o in ctx.all_options() if o.var is not None]
    variables += [*ctx.cancelled.values(), *ctx.units.values(), *ctx.moved.values()]
    return variables + list(ctx.move_start.values())


def _hint_cancel_everything(ctx: DecisionVars) -> None:
    """A starting point that is feasible whenever the problem is: cancel every affected class."""
    cancelled = {var.index for var in ctx.cancelled.values()}
    for var in _all_variables(ctx):
        ctx.model.add_hint(var, 1 if var.index in cancelled else 0)


def _hint_plan(ctx: DecisionVars, plan: Plan) -> None:
    """Start the search from `plan`; anything the plan does not use is hinted to 0."""
    placed = {(a.activity_id, a.room_id, a.start_min) for a in plan.assignments}
    moves = {(m.activity_id, m.pool_id): m for m in plan.moves}
    values = {var.index: 0 for var in _all_variables(ctx)}
    for activity_id, options in ctx.options.items():
        for o in options:
            if o.var is not None and (activity_id, o.room.id, o.start) in placed:
                values[o.var.index] = 1
    for activity_id in plan.cancelled & set(ctx.cancelled):
        values[ctx.cancelled[activity_id].index] = 1
    for key, move in moves.items():
        if key in ctx.moved:
            values[ctx.moved[key].index] = 1
            values[ctx.units[key].index] = move.units
            values[ctx.move_start[key].index] = move.start_min
    for var in _all_variables(ctx):
        ctx.model.add_hint(var, values[var.index])


def _hint_solution(ctx: DecisionVars, solver: cp_model.CpSolver) -> None:
    ctx.model.clear_hints()  # type: ignore[no-untyped-call]  # ortools ships no annotation
    for var in _all_variables(ctx):
        ctx.model.add_hint(var, solver.value(var))


def _extract_plan(ctx: DecisionVars, solver: cp_model.CpSolver, version: int) -> Plan:
    problem = ctx.problem
    assignments = tuple(
        Assignment(activity_id=o.activity.id, room_id=o.room.id, start_min=o.start)
        for activity_id, options in ctx.options.items()
        if activity_id in problem.movable_activity_ids
        for o in options
        if o.var is not None and solver.boolean_value(o.var)
    )
    cancelled = frozenset(a for a, var in ctx.cancelled.items() if solver.boolean_value(var))
    moves = []
    for key, moved in ctx.moved.items():
        if solver.boolean_value(moved):
            units, start = solver.value(ctx.units[key]), solver.value(ctx.move_start[key])
            pool = problem.campus.pool(key[1])
            moves.append(
                EquipmentMove(
                    pool_id=key[1],
                    activity_id=key[0],
                    units=units,
                    start_min=start,
                    end_min=start + move_minutes(pool, units),
                )
            )
    return Plan(
        based_on_version=version, assignments=assignments, cancelled=cancelled, moves=tuple(moves)
    )
