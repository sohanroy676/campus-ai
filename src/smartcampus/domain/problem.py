"""The recovery problem a plan is checked against (built by `impact/`; tests build it directly)."""

from functools import cached_property
from typing import Self

from pydantic import Field, model_validator

from smartcampus.domain.base import FrozenModel
from smartcampus.domain.entities import Activity, Campus, Cohort, Faculty, Fault, SafetyHold
from smartcampus.domain.time import Interval


class Provenance(FrozenModel):
    """How a generated scenario was made; with the solver settings it repeats a run exactly."""

    generator_version: str
    seed: int
    size: str
    load: int
    severity: str


class RecoveryProblem(FrozenModel):
    campus: Campus
    cohorts: tuple[Cohort, ...]
    faculty: tuple[Faculty, ...]
    activities: tuple[Activity, ...]
    faults: tuple[Fault, ...] = ()
    holds: tuple[SafetyHold, ...] = ()
    movable_activity_ids: frozenset[str]
    window: Interval
    plan_time_min: int = Field(ge=0)
    staff_available: int = Field(default=2, ge=1)
    prior_moves_this_week: dict[str, int] = Field(default_factory=dict)
    provenance: Provenance | None = None  # set by the generator; hand-made scenarios leave it out

    @model_validator(mode="after")
    def _check_references(self) -> Self:
        activity_ids = [a.id for a in self.activities]
        cohort_ids = [c.id for c in self.cohorts]
        faculty_ids = [f.id for f in self.faculty]
        for kind, ids in (
            ("activity", activity_ids),
            ("cohort", cohort_ids),
            ("faculty", faculty_ids),
        ):
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {kind} ids")
        if not self.movable_activity_ids <= set(activity_ids):
            raise ValueError("movable_activity_ids must be activities of the problem")
        room_ids = {r.id for r in self.campus.rooms}
        pool_ids = {p.id for p in self.campus.pools}
        for activity in self.activities:
            if activity.cohort_id not in cohort_ids:
                raise ValueError(f"activity {activity.id} has unknown cohort {activity.cohort_id}")
            if not set(activity.faculty_ids) <= set(faculty_ids):
                raise ValueError(f"activity {activity.id} has unknown faculty")
            if activity.room_id not in room_ids:
                raise ValueError(f"activity {activity.id} is in unknown room {activity.room_id}")
        if any(f.room_id not in room_ids for f in self.faults):
            raise ValueError("fault in unknown room")
        for hold in self.holds:
            known = room_ids if hold.target_kind == "room" else pool_ids
            if hold.target_id not in known:
                raise ValueError(f"hold on unknown {hold.target_kind} {hold.target_id}")
        return self

    @cached_property
    def _activities_by_id(self) -> dict[str, Activity]:
        return {a.id: a for a in self.activities}

    @cached_property
    def _cohorts_by_id(self) -> dict[str, Cohort]:
        return {c.id: c for c in self.cohorts}

    def activity(self, activity_id: str) -> Activity:
        return self._activities_by_id[activity_id]

    def cohort(self, cohort_id: str) -> Cohort:
        return self._cohorts_by_id[cohort_id]
