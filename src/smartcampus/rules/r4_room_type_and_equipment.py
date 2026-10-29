"""R4 room_type_and_equipment: allowed room type, and enough usable equipment units.

Units present in the room (pools on hold excluded) plus units moved in from other rooms must cover
each required equipment type. Pools with `movable = false` never move.
"""

from collections import Counter

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    Placement,
    counts_as_moved_in,
    known_moves,
    placements,
    remaining_equipment_need,
)
from smartcampus.rules.base import RuleId, Violation


def has_wrong_type(placement: Placement) -> bool:
    return placement.room.type not in placement.activity.allowed_room_types


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out: list[Violation] = []
    moves = known_moves(problem, plan)
    for p in placements(problem, plan):
        if has_wrong_type(p):
            out.append(
                Violation(
                    RuleId.R4,
                    f"room {p.room.id} is a {p.room.type}, not allowed for {p.activity.id}",
                    (p.activity.id,),
                    (p.room.id,),
                )
            )
        for eq_type, missing in sorted(remaining_equipment_need(problem, p).items()):
            moved_in = sum(
                m.units
                for m, pool, act in moves
                if act.id == p.activity.id and counts_as_moved_in(pool, eq_type, p.room.id)
            )
            if moved_in < missing:
                out.append(
                    Violation(
                        RuleId.R4,
                        f"{p.activity.id} in {p.room.id} lacks {missing - moved_in} unit(s) "
                        f"of {eq_type}",
                        (p.activity.id,),
                        (p.room.id,),
                    )
                )
    pools = {pool.id for pool in problem.campus.pools}
    for m in plan.moves:
        if m.pool_id not in pools:
            out.append(Violation(RuleId.R4, f"move of unknown pool {m.pool_id}", (m.activity_id,)))
        elif m.activity_id not in problem.movable_activity_ids:
            out.append(
                Violation(
                    RuleId.R4, f"move for unaffected activity {m.activity_id}", (m.activity_id,)
                )
            )
    for (pool_id, activity_id), n in sorted(
        Counter((m.pool_id, m.activity_id) for m in plan.moves).items()
    ):
        if n > 1:
            out.append(
                Violation(
                    RuleId.R4,
                    f"{n} moves of pool {pool_id} for {activity_id}; at most one is allowed",
                    (activity_id,),
                )
            )
    for m, pool, act in moves:
        if not pool.movable:
            out.append(Violation(RuleId.R4, f"pool {pool.id} is not movable", (act.id,)))
        if m.units > pool.units:
            out.append(
                Violation(
                    RuleId.R4,
                    f"move of {m.units} units exceeds the {pool.units} in pool {pool.id}",
                    (act.id,),
                )
            )
    return out
