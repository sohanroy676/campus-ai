"""Event schemas for the append-only log. Schemas only; `sim/` owns writing them."""

from typing import Annotated, Literal

from pydantic import Field

from smartcampus.domain.base import FrozenModel
from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.plan import Plan


class _EventBase(FrozenModel):
    version: int = Field(ge=0)
    at_min: int = Field(ge=0)


class FaultOccurred(_EventBase):
    type: Literal["fault_occurred"] = "fault_occurred"
    fault: Fault


class RepairOverrun(_EventBase):
    type: Literal["repair_overrun"] = "repair_overrun"
    fault_id: str
    new_end_min: int = Field(ge=0)


class SafetyHoldPlaced(_EventBase):
    type: Literal["safety_hold_placed"] = "safety_hold_placed"
    hold: SafetyHold


class PlanApplied(_EventBase):
    type: Literal["plan_applied"] = "plan_applied"
    plan: Plan


Event = Annotated[
    FaultOccurred | RepairOverrun | SafetyHoldPlaced | PlanApplied,
    Field(discriminator="type"),
]
