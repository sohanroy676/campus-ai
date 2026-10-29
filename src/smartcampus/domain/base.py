"""Shared Pydantic base class: immutable, no unknown fields."""

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
