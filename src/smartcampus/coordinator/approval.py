"""Approval triggers (docs/model-spec.md section 6). Policy on top of a valid plan, not a hard rule.

A plan that fires any trigger needs a timetabling officer's approval before it is applied.
"""

from enum import StrEnum

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.solver.objective import (
    LATE_CHANGE_MIN,
    changes_building,
    evaluate,
    is_changed,
)

MAX_PEOPLE_MOVED_WITHOUT_APPROVAL = 100


class Trigger(StrEnum):
    CANCELLATION = "cancellation"
    PEOPLE_MOVED = "people_moved"
    CROSS_BUILDING = "cross_building"
    LATE_CHANGE = "late_change"
    SAFETY_HOLD = "safety_hold"


def triggers(problem: RecoveryProblem, plan: Plan) -> tuple[Trigger, ...]:
    """The triggers `plan` fires, in a fixed order; empty if it can be applied directly."""
    fired: list[Trigger] = []
    if plan.cancelled:
        fired.append(Trigger.CANCELLATION)
    if evaluate(problem, plan).people_moved > MAX_PEOPLE_MOVED_WITHOUT_APPROVAL:
        fired.append(Trigger.PEOPLE_MOVED)
    changed = [
        (problem.activity(a.activity_id), a.room_id, a.start_min)
        for a in plan.assignments
        if a.activity_id in problem.movable_activity_ids
    ]
    changed = [(act, room, start) for act, room, start in changed if is_changed(act, room, start)]
    if any(changes_building(problem, act, room) for act, room, _ in changed):
        fired.append(Trigger.CROSS_BUILDING)
    touched = [act for act, _, _ in changed] + [
        problem.activity(a) for a in plan.cancelled if a in problem.movable_activity_ids
    ]
    if any(act.start_min - problem.plan_time_min < LATE_CHANGE_MIN for act in touched):
        fired.append(Trigger.LATE_CHANGE)
    if problem.holds:
        fired.append(Trigger.SAFETY_HOLD)
    return tuple(fired)
