"""Event schemas for the append-only log. Schemas only; `sim/` owns writing them."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

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


class Approval(FrozenModel):
    """Who let a plan through the approval triggers (spec section 6), and which triggers fired.

    Recorded inside `PlanApplied` rather than as its own event: an extra event would change the
    state version and make the plan it approves stale.
    """

    approver: Literal["not_needed", "auto", "officer"]
    triggers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _triggers_need_a_decision(self) -> Self:
        if self.approver == "not_needed" and self.triggers:
            raise ValueError("a plan that fired approval triggers cannot be marked not_needed")
        return self


class PlanApplied(_EventBase):
    type: Literal["plan_applied"] = "plan_applied"
    plan: Plan
    approval: Approval | None = None  # None for plans applied without the approval step


Event = Annotated[
    FaultOccurred | RepairOverrun | SafetyHoldPlaced | PlanApplied,
    Field(discriminator="type"),
]
