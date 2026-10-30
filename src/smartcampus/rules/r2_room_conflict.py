"""R2 room_conflict: a room hosts at most one activity per slot, and a closed room hosts none."""

from collections import defaultdict

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    Placement,
    intervals_overlap,
    placements,
    room_closures,
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
    found = placements(problem, plan)
    closures = room_closures(problem)
    # Violations are keyed (i, j): a closed room is (i, -1), a double booking of i < j is (i, j).
    # Sorting by key gives the order of a loop over all i < j. Per room, sort by start and sweep.
    keyed: list[tuple[int, int, Violation]] = []
    by_room: dict[str, list[int]] = defaultdict(list)
    for i, p in enumerate(found):
        by_room[p.room.id].append(i)
        if any(intervals_overlap(p.start, p.end, s, e) for s, e in closures.get(p.room.id, ())):
            keyed.append(
                (
                    i,
                    -1,
                    Violation(
                        RuleId.R2,
                        f"room {p.room.id} is closed while {p.activity.id} is held there",
                        (p.activity.id,),
                        (p.room.id,),
                    ),
                )
            )
    for indices in by_room.values():
        indices.sort(key=lambda k: found[k].start)
        for pos, a in enumerate(indices):
            end = found[a].end
            for b in indices[pos + 1 :]:
                if found[b].start >= end:
                    break
                i, j = min(a, b), max(a, b)
                ids = tuple(sorted((found[i].activity.id, found[j].activity.id)))
                room_id = found[i].room.id
                message = f"room {room_id} hosts {ids[0]} and {ids[1]} at the same time"
                keyed.append((i, j, Violation(RuleId.R2, message, ids, (room_id,))))
    keyed.sort(key=lambda item: (item[0], item[1]))
    return [violation for _, _, violation in keyed]


def post(ctx: DecisionVars) -> None:
    by_room_slot: dict[tuple[str, int], list[Placement]] = defaultdict(list)
    for option in ctx.all_options():
        if is_closed(ctx.problem, option):
            ctx.forbid(option, RuleId.R2)
        for slot in option.slots:
            by_room_slot[(option.room.id, slot)].append(option)
    for options in by_room_slot.values():
        ctx.at_most_one(options, RuleId.R2)
