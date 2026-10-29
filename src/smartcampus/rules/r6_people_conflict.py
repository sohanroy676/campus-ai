"""R6 people_conflict: nobody is in two places at once, and back-to-back travel is short enough.

Two classes with a common cohort or faculty member may not overlap. If one ends exactly when the
other starts, their buildings must be at most 10 minutes apart.
"""

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    MAX_BACK_TO_BACK_TRAVEL_MIN,
    Placement,
    intervals_overlap,
    placements,
)
from smartcampus.rules.base import RuleId, Violation


def shares_person(first: Placement, second: Placement) -> bool:
    a, b = first.activity, second.activity
    return a.cohort_id == b.cohort_id or bool(set(a.faculty_ids) & set(b.faculty_ids))


def is_too_far(problem: RecoveryProblem, first: Placement, second: Placement) -> bool:
    """Back-to-back in either order with a walk longer than the allowed gap."""
    back_to_back = first.end == second.start or second.end == first.start
    walk = problem.campus.travel_minutes(first.room.building_id, second.room.building_id)
    return back_to_back and walk > MAX_BACK_TO_BACK_TRAVEL_MIN


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out: list[Violation] = []
    found = placements(problem, plan)
    for i, p in enumerate(found):
        for q in found[i + 1 :]:
            if not shares_person(p, q):
                continue
            ids = tuple(sorted((p.activity.id, q.activity.id)))
            rooms = tuple(sorted({p.room.id, q.room.id}))
            if intervals_overlap(p.start, p.end, q.start, q.end):
                out.append(
                    Violation(
                        RuleId.R6, f"{ids[0]} and {ids[1]} share a person and overlap", ids, rooms
                    )
                )
            elif is_too_far(problem, p, q):
                out.append(
                    Violation(
                        RuleId.R6,
                        f"{ids[0]} and {ids[1]} are back-to-back with more than "
                        f"{MAX_BACK_TO_BACK_TRAVEL_MIN} minutes between buildings",
                        ids,
                        rooms,
                    )
                )
    return out
