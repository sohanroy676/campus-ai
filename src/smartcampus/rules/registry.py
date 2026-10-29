"""The eight hard rules in R1..R8 order."""

from collections.abc import Callable
from dataclasses import dataclass

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules import (
    r1_assignment,
    r2_room_conflict,
    r3_capacity,
    r4_room_type_and_equipment,
    r5_move_lead_time,
    r6_people_conflict,
    r7_accessibility,
    r8_safety_hold,
)
from smartcampus.rules.base import RuleId, Violation
from smartcampus.rules.variables import DecisionVars


@dataclass(frozen=True)
class HardRule:
    id: RuleId
    name: str
    check: Callable[[RecoveryProblem, Plan], list[Violation]]
    post: Callable[[DecisionVars], None]


ALL_RULES: tuple[HardRule, ...] = (
    HardRule(RuleId.R1, "assignment", r1_assignment.check, r1_assignment.post),
    HardRule(RuleId.R2, "room_conflict", r2_room_conflict.check, r2_room_conflict.post),
    HardRule(RuleId.R3, "capacity", r3_capacity.check, r3_capacity.post),
    HardRule(
        RuleId.R4,
        "room_type_and_equipment",
        r4_room_type_and_equipment.check,
        r4_room_type_and_equipment.post,
    ),
    HardRule(RuleId.R5, "move_lead_time", r5_move_lead_time.check, r5_move_lead_time.post),
    HardRule(RuleId.R6, "people_conflict", r6_people_conflict.check, r6_people_conflict.post),
    HardRule(RuleId.R7, "accessibility", r7_accessibility.check, r7_accessibility.post),
    HardRule(RuleId.R8, "safety_hold", r8_safety_hold.check, r8_safety_hold.post),
)

RULES_BY_ID: dict[RuleId, HardRule] = {rule.id: rule for rule in ALL_RULES}
