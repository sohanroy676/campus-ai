"""R7 accessibility: a cohort that needs step-free access only gets step-free rooms."""

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import Placement, placements
from smartcampus.rules.base import RuleId, Violation


def lacks_step_free(problem: RecoveryProblem, placement: Placement) -> bool:
    return problem.cohort(placement.activity.cohort_id).step_free_required and (
        not placement.room.step_free
    )


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    return [
        Violation(
            RuleId.R7,
            f"cohort {p.activity.cohort_id} needs step-free access but {p.room.id} has none",
            (p.activity.id,),
            (p.room.id,),
        )
        for p in placements(problem, plan)
        if lacks_step_free(problem, p)
    ]
