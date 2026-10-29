"""R3 capacity: room.capacity >= cohort.size."""

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import Placement, placements
from smartcampus.rules.base import RuleId, Violation


def is_too_small(problem: RecoveryProblem, placement: Placement) -> bool:
    return placement.room.capacity < problem.cohort(placement.activity.cohort_id).size


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    return [
        Violation(
            RuleId.R3,
            f"room {p.room.id} seats {p.room.capacity} but cohort "
            f"{p.activity.cohort_id} has {problem.cohort(p.activity.cohort_id).size}",
            (p.activity.id,),
            (p.room.id,),
        )
        for p in placements(problem, plan)
        if is_too_small(problem, p)
    ]
