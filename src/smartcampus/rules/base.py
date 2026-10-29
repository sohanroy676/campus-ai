"""Rule identifiers and the violation record every rule check returns."""

from dataclasses import dataclass
from enum import StrEnum


class RuleId(StrEnum):
    R1 = "R1"  # assignment
    R2 = "R2"  # room_conflict
    R3 = "R3"  # capacity
    R4 = "R4"  # room_type_and_equipment
    R5 = "R5"  # move_lead_time
    R6 = "R6"  # people_conflict
    R7 = "R7"  # accessibility
    R8 = "R8"  # safety_hold


@dataclass(frozen=True)
class Violation:
    rule: RuleId
    message: str
    activity_ids: tuple[str, ...] = ()
    room_ids: tuple[str, ...] = ()
