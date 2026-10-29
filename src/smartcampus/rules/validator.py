"""Plan validator: runs every hard rule against a plan."""

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.base import Violation
from smartcampus.rules.registry import ALL_RULES


class PlanInvalidError(Exception):
    """A plan produced by the system broke a hard rule. This is a bug, not a user error."""

    def __init__(self, violations: list[Violation]) -> None:
        self.violations = violations
        summary = "; ".join(f"{v.rule}: {v.message}" for v in violations)
        super().__init__(f"plan breaks {len(violations)} hard rule(s): {summary}")


def validate(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    return [v for rule in ALL_RULES for v in rule.check(problem, plan)]


def assert_valid(problem: RecoveryProblem, plan: Plan) -> None:
    violations = validate(problem, plan)
    if violations:
        raise PlanInvalidError(violations)
