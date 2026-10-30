"""Run one scenario with one method: log the disruption, plan, check, apply the plan as an event."""

import time
from dataclasses import dataclass
from enum import StrEnum

from smartcampus.agents.contract_net import contract_net
from smartcampus.baselines.greedy import greedy
from smartcampus.baselines.resolve import resolve_from_scratch, resolve_settings
from smartcampus.baselines.sequential import sequential
from smartcampus.domain.events import FaultOccurred, PlanApplied, SafetyHoldPlaced
from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.validator import assert_valid
from smartcampus.sim.store import EventStore
from smartcampus.solver.objective import StageValues, evaluate
from smartcampus.solver.solve import SolverSettings, StageReport, solve


class Method(StrEnum):
    JOINT = "joint"
    GREEDY = "greedy"
    RESOLVE = "resolve"
    SEQUENTIAL = "sequential"
    CONTRACT_NET = "contract_net"


@dataclass(frozen=True)
class RunResult:
    method: Method
    problem: RecoveryProblem  # as rebuilt from the event log
    plan: Plan  # as applied (status "applied")
    values: StageValues
    stages: tuple[StageReport, ...]  # empty for methods that do not solve in stages
    settings: SolverSettings | None  # None for methods without solver settings
    log_version: int  # events in the log after the plan was applied
    planning_seconds: float = 0.0  # wall time to build the plan, start plan included
    start_plan_seconds: float = 0.0  # of which the greedy start plan (joint only)


def seed_disruptions(store: EventStore, problem: RecoveryProblem) -> None:
    """Append the scenario's faults and holds to an empty log, all at plan time."""
    if store.version != 0:
        raise ValueError("disruptions can only be seeded into an empty event log")
    at_min = problem.plan_time_min
    for fault in problem.faults:
        store.append(FaultOccurred(version=store.version, at_min=at_min, fault=fault))
    for hold in problem.holds:
        store.append(SafetyHoldPlaced(version=store.version, at_min=at_min, hold=hold))


@dataclass(frozen=True)
class Planned:
    plan: Plan
    stages: tuple[StageReport, ...]
    settings: SolverSettings | None
    planning_seconds: float
    start_plan_seconds: float


def plan_with_method(
    current: RecoveryProblem,
    method: Method,
    version: int,
    settings: SolverSettings | None = None,
) -> Planned:
    """Build and independently re-check a plan for `current`; nothing is written to the log."""
    started = time.monotonic()
    start_plan_seconds = 0.0
    stages: tuple[StageReport, ...] = ()
    used_settings: SolverSettings | None = None
    if method is Method.JOINT:
        used_settings = settings or SolverSettings.for_problem(current)
        # The greedy plan is complete, so the search starts from a plan instead of from nothing.
        start = greedy(current, based_on_version=version)
        start_plan_seconds = time.monotonic() - started
        solved = solve(current, used_settings, based_on_version=version, hint=start)
        plan, stages = solved.plan, solved.stages
    elif method is Method.RESOLVE:
        tier = settings or SolverSettings.for_problem(current)
        used_settings = resolve_settings(tier)
        solved = resolve_from_scratch(current, tier, based_on_version=version)
        plan, stages = solved.plan, solved.stages
    elif method is Method.SEQUENTIAL:
        used_settings = settings or SolverSettings.for_problem(current)
        solved = sequential(current, used_settings, based_on_version=version)
        plan, stages = solved.plan, solved.stages
    elif method is Method.CONTRACT_NET:
        used_settings = settings or SolverSettings.for_problem(current)
        limit = sum(used_settings.stage_seconds)  # the tier's total, as for the solver methods
        plan = contract_net(current, time_limit_seconds=limit, based_on_version=version)
    else:
        plan = greedy(current, based_on_version=version)

    planning_seconds = time.monotonic() - started
    assert_valid(current, plan)  # independent re-check with the shared rule library
    return Planned(plan, stages, used_settings, planning_seconds, start_plan_seconds)


def run_scenario(
    problem: RecoveryProblem,
    method: Method,
    store: EventStore,
    settings: SolverSettings | None = None,
) -> RunResult:
    """Plan against the state in `store`, then append the plan as the next event.

    Raises `InfeasibleInputError` or `NoSolutionError` when there is no plan, and
    `PlanInvalidError` if the plan breaks a hard rule (a bug, not bad input).
    """
    base = RecoveryProblem.model_validate({**dict(problem), "faults": (), "holds": ()})
    seed_disruptions(store, problem)
    current = store.state.problem(base)
    planned = plan_with_method(current, method, store.version, settings)
    plan = planned.plan
    store.append(PlanApplied(version=store.version, at_min=current.plan_time_min, plan=plan))
    [applied] = store.state.applied_plans
    return RunResult(
        method=method,
        problem=current,
        plan=applied,
        values=evaluate(current, plan),
        stages=planned.stages,
        settings=planned.settings,
        log_version=store.version,
        planning_seconds=planned.planning_seconds,
        start_plan_seconds=planned.start_plan_seconds,
    )
