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
