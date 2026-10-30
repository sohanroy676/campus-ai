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
from smartcampus.eval.metrics import (
    NO_PLAN,
    PLAN,
    RunRecord,
    cancel_everything_values,
)
from smartcampus.generator.scenario import load_scenario
from smartcampus.sim.store import EventStore
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
    instance: str, problem: RecoveryProblem, method: Method, *, commit: str = ""
) -> RunRecord:
    """Run `method` on `problem`; `PlanInvalidError` (a bug) is not caught."""
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
    wanted = {p.stem for p in paths}
    with results_path.open("a", encoding="utf-8", newline="\n") as results:
        for path in paths:
            todo = [m for m in methods if (path.stem, m.value) not in done]
            if not todo:
                continue
            problem = load_scenario(path)
            for method in todo:
                record = run_one(path.stem, problem, method, commit=commit)
                results.write(record.to_json() + "\n")
                results.flush()
                records.append(record)
                if progress is not None:
                    progress(f"{path.stem} {method.value}: {record.status} {record.seconds:.1f}s")
    wanted_methods = {m.value for m in methods}
    return [r for r in records if r.instance in wanted and r.method in wanted_methods]
