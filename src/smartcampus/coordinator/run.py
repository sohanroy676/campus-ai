"""Run one scenario with one method: log the disruption, plan, check, apply the plan as an event."""

from dataclasses import dataclass
from enum import StrEnum

from smartcampus.baselines.greedy import greedy
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


@dataclass(frozen=True)
class RunResult:
    method: Method
    problem: RecoveryProblem  # as rebuilt from the event log
    plan: Plan  # as applied (status "applied")
    values: StageValues
    stages: tuple[StageReport, ...]  # empty for methods that do not solve in stages
    settings: SolverSettings | None  # None for methods without solver settings
    log_version: int  # events in the log after the plan was applied


def seed_disruptions(store: EventStore, problem: RecoveryProblem) -> None:
    """Append the scenario's faults and holds to an empty log, all at plan time."""
    if store.version != 0:
        raise ValueError("disruptions can only be seeded into an empty event log")
    at_min = problem.plan_time_min
    for fault in problem.faults:
        store.append(FaultOccurred(version=store.version, at_min=at_min, fault=fault))
    for hold in problem.holds:
        store.append(SafetyHoldPlaced(version=store.version, at_min=at_min, hold=hold))


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
    version = store.version

    stages: tuple[StageReport, ...] = ()
    used_settings: SolverSettings | None = None
    if method is Method.JOINT:
        used_settings = settings or SolverSettings.for_problem(problem)
        # The greedy plan is complete, so the search starts from a plan instead of from nothing.
        start = greedy(current, based_on_version=version)
        solved = solve(current, used_settings, based_on_version=version, hint=start)
        plan, stages = solved.plan, solved.stages
    else:
        plan = greedy(current, based_on_version=version)

    assert_valid(current, plan)  # independent re-check with the shared rule library
    store.append(PlanApplied(version=store.version, at_min=current.plan_time_min, plan=plan))
    [applied] = store.state.applied_plans
    return RunResult(
        method=method,
        problem=current,
        plan=applied,
        values=evaluate(current, plan),
        stages=stages,
        settings=used_settings,
        log_version=store.version,
    )
