"""R8 safety_hold: a room or equipment pool on hold is unusable for the whole hold.

A room on hold hosts nothing while the hold overlaps the class. A pool on hold cannot be moved
anywhere between the move start and the end of the class it is moved for. (Held pools already
in a room are excluded from R4's unit count.)
"""

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    Placement,
    known_moves,
    placements,
    plan_placements,
    pool_hold_overlaps,
    room_hold_overlaps,
)
from smartcampus.rules.base import RuleId, Violation


def is_on_hold(problem: RecoveryProblem, placement: Placement) -> bool:
    return room_hold_overlaps(problem, placement.room.id, placement.start, placement.end)


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out = [
        Violation(
            RuleId.R8,
            f"room {p.room.id} is on safety hold while {p.activity.id} is held there",
            (p.activity.id,),
            (p.room.id,),
        )
        for p in placements(problem, plan)
        if is_on_hold(problem, p)
    ]
    placed = plan_placements(problem, plan)
    for m, pool, act in known_moves(problem, plan):
        for p in placed:
            if p.activity.id == act.id and pool_hold_overlaps(problem, pool.id, m.start_min, p.end):
                out.append(
                    Violation(
                        RuleId.R8,
                        f"pool {pool.id} is on safety hold during its move for {act.id}",
                        (act.id,),
                    )
                )
    return out
