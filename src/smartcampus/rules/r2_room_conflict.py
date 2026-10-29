"""R2 room_conflict: a room hosts at most one activity per slot, and a closed room hosts none."""

from collections import defaultdict

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    Placement,
    intervals_overlap,
    placements,
    room_fault_overlaps,
    room_hold_overlaps,
)
from smartcampus.rules.base import RuleId, Violation
from smartcampus.rules.variables import DecisionVars


def is_closed(problem: RecoveryProblem, placement: Placement) -> bool:
    """An active fault or a safety hold overlaps the placement."""
    room_id, start, end = placement.room.id, placement.start, placement.end
    return room_fault_overlaps(problem, room_id, start, end) or room_hold_overlaps(
        problem, room_id, start, end
    )


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out: list[Violation] = []
    found = placements(problem, plan)
    for i, p in enumerate(found):
        if is_closed(problem, p):
            out.append(
                Violation(
                    RuleId.R2,
                    f"room {p.room.id} is closed while {p.activity.id} is held there",
                    (p.activity.id,),
                    (p.room.id,),
                )
            )
        for q in found[i + 1 :]:
            if p.room.id == q.room.id and intervals_overlap(p.start, p.end, q.start, q.end):
                ids = tuple(sorted((p.activity.id, q.activity.id)))
                out.append(
                    Violation(
                        RuleId.R2,
                        f"room {p.room.id} hosts {ids[0]} and {ids[1]} at the same time",
                        ids,
                        (p.room.id,),
                    )
                )
    return out


def post(ctx: DecisionVars) -> None:
    by_room_slot: dict[tuple[str, int], list[Placement]] = defaultdict(list)
    for option in ctx.all_options():
        if is_closed(ctx.problem, option):
            ctx.forbid(option, RuleId.R2)
        for slot in option.slots:
            by_room_slot[(option.room.id, slot)].append(option)
    for options in by_room_slot.values():
        ctx.at_most_one(options, RuleId.R2)
