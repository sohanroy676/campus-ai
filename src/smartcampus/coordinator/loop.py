"""The recovery loop: plan, check the approval triggers, apply, and re-plan after a later event.

Each later event is appended to the log; any plan not yet applied is then stale (ADR 0003) and a
new plan is built from the state the log now describes (`replan_problem`).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from smartcampus.coordinator.approval import Trigger, triggers
from smartcampus.coordinator.replan import replan_problem
from smartcampus.coordinator.run import Method, Planned, plan_with_method, seed_disruptions
from smartcampus.domain.events import Approval, Event, PlanApplied
from smartcampus.domain.plan import Plan, PlanStatus
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.sim.store import EventStore
from smartcampus.solver.objective import StageValues, evaluate
from smartcampus.solver.solve import SolverSettings

type Approver = Literal["not_needed", "auto", "officer"]


@dataclass(frozen=True)
class Round:
    problem: RecoveryProblem  # what this round planned against
    plan: Plan  # status: applied, pending_approval or stale
    triggers: tuple[Trigger, ...]
    approver: Approver | None  # None if the plan was not applied
    values: StageValues
    planned: Planned
    log_version: int  # events in the log when the round ended


def recover(
    problem: RecoveryProblem,
    store: EventStore,
    method: Method,
    followups: Sequence[Event] = (),
    *,
    auto_approve: bool = True,
    settings: SolverSettings | None = None,
) -> list[Round]:
    """Run the scenario, then each follow-up event in turn; one `Round` per plan built.

    A plan that fires a trigger is applied only if `auto_approve` (demo mode, logged as "auto").
    Otherwise it stays `pending_approval`; the next follow-up event makes it `stale` and a new
    plan is built. With no follow-up left, the loop stops with the plan pending.
    """
    base = RecoveryProblem.model_validate({**dict(problem), "faults": (), "holds": ()})
    seed_disruptions(store, problem)
    current = store.state.problem(base)
    rounds: list[Round] = []
    pending = list(followups)
    while True:
        planned = plan_with_method(current, method, store.version, settings)
        fired = triggers(current, planned.plan)
        approver: Approver | None = "not_needed" if not fired else "auto" if auto_approve else None
        if approver is not None:
            store.append(
                PlanApplied(
                    version=store.version,
                    at_min=current.plan_time_min,
                    plan=planned.plan,
                    approval=Approval(approver=approver, triggers=tuple(fired)),
                )
            )
            status = PlanStatus.APPLIED
        else:
            status = PlanStatus.PENDING_APPROVAL
        if pending and status is PlanStatus.PENDING_APPROVAL:
            status = PlanStatus.STALE  # the next event arrives before anyone approves it
        plan = planned.plan.model_copy(update={"status": status})
        rounds.append(
            Round(
                current,
                plan,
                fired,
                approver,
                evaluate(current, planned.plan),
                planned,
                store.version,
            )
        )
        if not pending:
            return rounds
        event = pending.pop(0)
        store.append(event.model_copy(update={"version": store.version}))
        current = replan_problem(base, store.state)
