"""Plan schema: assignments, cancellations and equipment moves.

A plan may be malformed (e.g. an activity both assigned and cancelled) so rule R1 can report it.
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from smartcampus.domain.base import FrozenModel


class PlanStatus(StrEnum):
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    APPLIED = "applied"
    STALE = "stale"
    REJECTED = "rejected"


class Assignment(FrozenModel):
    activity_id: str
    room_id: str
    start_min: int


class EquipmentMove(FrozenModel):
    """`units` of pool `pool_id` carried to `activity_id`'s room during `[start_min, end_min)`."""

    pool_id: str
    activity_id: str
    units: int = Field(gt=0)
    start_min: int
    end_min: int

    @model_validator(mode="after")
    def _start_before_end(self) -> Self:
        if self.end_min <= self.start_min:
            raise ValueError("a move must end after it starts")
        return self


class Plan(FrozenModel):
    based_on_version: int = Field(ge=0)
    assignments: tuple[Assignment, ...] = ()
    cancelled: frozenset[str] = frozenset()
    moves: tuple[EquipmentMove, ...] = ()
    status: PlanStatus = PlanStatus.PROPOSED
