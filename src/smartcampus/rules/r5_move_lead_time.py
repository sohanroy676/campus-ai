"""R5 move_lead_time: equipment moves finish before class, from plan time, within mover capacity.

A move occupies one mover for `units x move_minutes_per_unit + 15` minutes (the setup buffer).
"""

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    WEEK_END_MIN,
    known_moves,
    move_minutes,
    plan_placements,
)
from smartcampus.rules.base import RuleId, Violation
from smartcampus.rules.variables import DecisionVars


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out: list[Violation] = []
    moves = known_moves(problem, plan)
    placed = plan_placements(problem, plan)
    for m, pool, act in moves:
        expected = move_minutes(pool, m.units)
        label = f"move of {pool.id} for {act.id}"
        if m.end_min - m.start_min != expected:
            out.append(
                Violation(
                    RuleId.R5, f"{label} takes {expected} minutes, not planned length", (act.id,)
                )
            )
        if m.start_min < problem.plan_time_min:
            out.append(Violation(RuleId.R5, f"{label} starts before plan time", (act.id,)))
        if m.end_min > WEEK_END_MIN:
            out.append(Violation(RuleId.R5, f"{label} ends after the week", (act.id,)))
        for p in placed:
            if p.activity.id == act.id and m.end_min > p.start:
                out.append(
                    Violation(RuleId.R5, f"{label} finishes after the class starts", (act.id,))
                )
    for start in sorted({m.start_min for m, _, _ in moves}):
        running = [a.id for m, _, a in moves if m.start_min <= start < m.end_min]
        if len(running) > problem.staff_available:
            out.append(
                Violation(
                    RuleId.R5,
                    f"{len(running)} moves run at minute {start}, only "
                    f"{problem.staff_available} movers available",
                    tuple(sorted(set(running))),
                )
            )
    return out


def post(ctx: DecisionVars) -> None:
    model, problem = ctx.model, ctx.problem
    lit = ctx.rule_lit[RuleId.R5]
    intervals = []
    for key, units in ctx.units.items():
        activity_id, pool_id = key
        moved, start = ctx.moved[key], ctx.move_start[key]
        pool = problem.campus.pool(pool_id)
        length = move_minutes(pool, units)
        end = model.new_int_var(0, WEEK_END_MIN + move_minutes(pool, pool.units), "move_end")
        model.add(end == start + length)  # a definition; the rule's limits are enforced below
        model.add(start >= problem.plan_time_min).only_enforce_if([moved, lit])
        model.add(end <= WEEK_END_MIN).only_enforce_if([moved, lit])
        earliest, _ = ctx.start_bounds(activity_id)
        model.add(end <= earliest).only_enforce_if([moved, lit])  # before every chosen start
        intervals.append(
            model.new_optional_interval_var(
                start, length, end, ctx.and_literal(moved, lit), f"move_{activity_id}_{pool_id}"
            )
        )
    model.add_cumulative(intervals, [1] * len(intervals), problem.staff_available)
