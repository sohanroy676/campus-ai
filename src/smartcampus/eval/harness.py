"""Run methods on a directory of scenarios and keep one record per (instance, method).

Each run uses a fresh in-memory event log, `num_workers=1` and `random_seed=42` (the tier's
settings). A method with no plan is recorded, not raised. Results are appended to
`<out>/results.jsonl` as they finish, so an interrupted evaluation resumes where it stopped.
"""

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from smartcampus.coordinator.run import Method, run_scenario
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.eval.manifest import check_or_write, current_environment
from smartcampus.eval.metrics import (
    NO_PLAN,
    PLAN,
    RunRecord,
    cancel_everything_values,
)
from smartcampus.generator.scenario import load_scenario
from smartcampus.sim.store import EventStore
from smartcampus.solver.objective import StageValues
from smartcampus.solver.solve import InfeasibleInputError, NoSolutionError, SolverSettings

RESULTS_FILE = "results.jsonl"


REPO_ROOT = Path(__file__).resolve().parents[3]


def code_version() -> str:
    """The git commit of the code, with "+dirty" if the working tree has uncommitted changes."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{head}+dirty" if status else head


def run_one(
    instance: str,
    problem: RecoveryProblem,
    method: Method,
    *,
    commit: str = "",
    start_values: StageValues | None = None,
) -> RunRecord:
    """Run `method` on `problem`; `PlanInvalidError` (a bug) is not caught.

    `start_values` are the greedy plan's values, the start solution every method is compared with
    for `start_unimproved` (greedy needs none).
    """
    provenance = problem.provenance
    generator_version = provenance.generator_version if provenance is not None else ""
    size, load, severity, seed = (
        (provenance.size, provenance.load, provenance.severity, provenance.seed)
        if provenance is not None
        else ("small", 0, "", 0)
    )
    imputed = cancel_everything_values(problem)
    try:
        with EventStore() as store:
            result = run_scenario(problem, method, store)
    except (NoSolutionError, InfeasibleInputError) as error:
        return RunRecord(
            instance=instance,
            size=size,
            load=load,
            severity=severity,
            seed=seed,
            method=method.value,
            status=NO_PLAN,
            values=None,
            imputed=imputed,
            seconds=0.0,
            start_plan_seconds=0.0,
            reason=f"{type(error).__name__}: {error}",
            limit_hit=isinstance(error, NoSolutionError),
            commit=commit,
            generator_version=generator_version,
            **_settings_fields(method, problem),
        )
    return RunRecord(
        instance=instance,
        size=size,
        load=load,
        severity=severity,
        seed=seed,
        method=method.value,
        status=PLAN,
        values=result.values,
        imputed=imputed,
        seconds=result.planning_seconds,
        start_plan_seconds=result.start_plan_seconds,
        limit_hit=result.limit_hit,
        start_unimproved=method is Method.GREEDY
        or (start_values is not None and result.values >= start_values),
        commit=commit,
        generator_version=generator_version,
        **_settings_fields(method, problem, result.settings),
    )


def _settings_fields(
    method: Method, problem: RecoveryProblem, used: SolverSettings | None = None
) -> dict[str, Any]:
    """Solver settings of a run. A run without a plan has no result, so its tier is rebuilt."""
    if method is Method.GREEDY:
        return {}
    settings = used or SolverSettings.for_problem(problem)
    return {
        "stage_seconds": list(settings.stage_seconds),
        "num_workers": settings.num_workers,
        "random_seed": settings.random_seed,
    }


def _greedy_first(methods: Sequence[Method]) -> list[Method]:
    return sorted(methods, key=lambda m: m is not Method.GREEDY)


def _recorded_greedy_values(instance: str, records: Sequence[RunRecord]) -> StageValues | None:
    for r in records:
        if r.instance == instance and r.method == Method.GREEDY.value:
            return r.values
    return None


def read_results(path: Path) -> list[RunRecord]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [RunRecord.from_json(line) for line in lines if line.strip()]


def run_eval(
    scenarios: Path,
    methods: Sequence[Method],
    out: Path,
    *,
    pattern: str = "*.json",
    progress: Callable[[str], None] | None = None,
) -> list[RunRecord]:
    """All records for the scenarios matching `pattern`, running only what `out` lacks."""
    paths = sorted(scenarios.glob(pattern))
    if not paths:
        raise ValueError(f"no scenarios match {pattern!r} in {scenarios}")
    out.mkdir(parents=True, exist_ok=True)
    results_path = out / RESULTS_FILE
    records = read_results(results_path)
    done = {(r.instance, r.method) for r in records}
    commit = code_version()
    check_or_write(out, commit, current_environment())
    wanted = {p.stem for p in paths}
    with results_path.open("a", encoding="utf-8", newline="\n") as results:
        for path in paths:
            # greedy first: its values are the start solution the others are compared with
            todo = [m for m in _greedy_first(methods) if (path.stem, m.value) not in done]
            if not todo:
                continue
            problem = load_scenario(path)
            start_values = _recorded_greedy_values(path.stem, records)
            if start_values is None and Method.GREEDY not in todo:
                start_values = run_one(path.stem, problem, Method.GREEDY, commit=commit).values
            for method in todo:
                record = run_one(
                    path.stem, problem, method, commit=commit, start_values=start_values
                )
                results.write(record.to_json() + "\n")
                results.flush()
                records.append(record)
                if method is Method.GREEDY:
                    start_values = record.values
                if progress is not None:
                    progress(f"{path.stem} {method.value}: {record.status} {record.seconds:.1f}s")
    wanted_methods = {m.value for m in methods}
    return [r for r in records if r.instance in wanted and r.method in wanted_methods]
