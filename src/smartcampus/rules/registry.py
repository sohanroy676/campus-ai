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


@dataclass(frozen=True)
class HardRule:
    id: RuleId
    name: str
    check: Callable[[RecoveryProblem, Plan], list[Violation]]


ALL_RULES: tuple[HardRule, ...] = (
    HardRule(RuleId.R1, "assignment", r1_assignment.check),
    HardRule(RuleId.R2, "room_conflict", r2_room_conflict.check),
    HardRule(RuleId.R3, "capacity", r3_capacity.check),
    HardRule(RuleId.R4, "room_type_and_equipment", r4_room_type_and_equipment.check),
    HardRule(RuleId.R5, "move_lead_time", r5_move_lead_time.check),
    HardRule(RuleId.R6, "people_conflict", r6_people_conflict.check),
    HardRule(RuleId.R7, "accessibility", r7_accessibility.check),
    HardRule(RuleId.R8, "safety_hold", r8_safety_hold.check),
)

RULES_BY_ID: dict[RuleId, HardRule] = {rule.id: rule for rule in ALL_RULES}
