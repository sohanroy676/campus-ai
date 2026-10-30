"""R1 assignment: every affected activity gets exactly one (room, start_slot), or is cancelled."""

from collections import Counter

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import valid_starts
from smartcampus.rules.base import RuleId, Violation
from smartcampus.rules.variables import DecisionVars


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out: list[Violation] = []
    movable = problem.movable_activity_ids
    counts = Counter(asg.activity_id for asg in plan.assignments)
    for activity_id in sorted(movable):
        placed, cancelled = counts[activity_id], activity_id in plan.cancelled
        if placed + cancelled == 1:
            continue
        if placed == 0:
            reason = "is neither assigned nor cancelled"
        elif cancelled:
            reason = "is both assigned and cancelled"
        else:
            reason = f"is assigned {placed} times"
        out.append(Violation(RuleId.R1, f"activity {activity_id} {reason}", (activity_id,)))
    for activity_id in sorted((set(counts) | plan.cancelled) - movable):
        out.append(
            Violation(
                RuleId.R1, f"activity {activity_id} is not an affected activity", (activity_id,)
            )
        )
    rooms = {r.id for r in problem.campus.rooms}
    starts_by_duration: dict[int, frozenset[int]] = {}  # valid starts depend on length only
    for asg in plan.assignments:
        if asg.activity_id not in movable:
            continue
        if asg.room_id not in rooms:
            out.append(
                Violation(
                    RuleId.R1, f"unknown room {asg.room_id}", (asg.activity_id,), (asg.room_id,)
                )
            )
            continue
        activity = problem.activity(asg.activity_id)
        if activity.duration_min not in starts_by_duration:
            starts_by_duration[activity.duration_min] = frozenset(valid_starts(problem, activity))
        if asg.start_min not in starts_by_duration[activity.duration_min]:
            out.append(
                Violation(
                    RuleId.R1,
                    f"activity {asg.activity_id} cannot start at minute {asg.start_min}: "
                    "not a slot inside the recovery window and a teaching day",
                    (asg.activity_id,),
                    (asg.room_id,),
                )
            )
    return out


def post(ctx: DecisionVars) -> None:
    lit = ctx.rule_lit[RuleId.R1]
    for activity_id in sorted(ctx.cancelled):
        placed = [o.var for o in ctx.options[activity_id] if o.var is not None]
        ctx.model.add(sum(placed) + ctx.cancelled[activity_id] == 1).only_enforce_if(lit)
