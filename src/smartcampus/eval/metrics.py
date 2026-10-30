"""One evaluation record per (instance, method), stored as one JSON line."""

import json
from dataclasses import asdict, dataclass
from typing import Any

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.solver.objective import StageValues, evaluate

METRICS = ("cancellations", "people_moved", "delay", "cost", "start_shift", "tie_break")
PLAN = "plan"
NO_PLAN = "no_plan"


@dataclass(frozen=True)
class RunRecord:
    instance: str  # scenario file stem
    size: str
    load: int
    severity: str
    seed: int
    method: str
    status: str  # PLAN or NO_PLAN
    values: StageValues | None  # None when there is no plan
    imputed: StageValues  # the instance's cancel-everything plan, used when a method has no plan
    seconds: float  # wall time to build the plan, start plan included
    start_plan_seconds: float  # of which the greedy start plan (joint only, else 0)
    reason: str = ""  # why there is no plan

    @property
    def solved(self) -> bool:
        return self.status == PLAN and self.values is not None

    def effective_values(self) -> StageValues:
        """The plan's values, or the cancel-everything values when there is no plan."""
        return self.values if self.values is not None else self.imputed

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, line: str) -> "RunRecord":
        data: dict[str, Any] = json.loads(line)
        values = data.pop("values")
        imputed = data.pop("imputed")
        return cls(
            values=StageValues(**values) if values is not None else None,
            imputed=StageValues(**imputed),
            **data,
        )


def cancel_everything_values(problem: RecoveryProblem) -> StageValues:
    """Score of cancelling every movable class: what a method without a plan is imputed with."""
    plan = Plan(
        based_on_version=0, assignments=(), cancelled=problem.movable_activity_ids, moves=()
    )
    return evaluate(problem, plan)


def metric(values: StageValues, name: str) -> int:
    return int(getattr(values, name))
