"""Run methods on a directory of scenarios and keep one record per (instance, method).

Each run uses a fresh in-memory event log, `num_workers=1` and `random_seed=42` (the tier's
settings). A method with no plan is recorded, not raised. Results are appended to
`<out>/results.jsonl` as they finish, so an interrupted evaluation resumes where it stopped.
"""

from collections.abc import Callable, Sequence
from pathlib import Path

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
from smartcampus.solver.solve import InfeasibleInputError, NoSolutionError

RESULTS_FILE = "results.jsonl"


def run_one(instance: str, problem: RecoveryProblem, method: Method) -> RunRecord:
    """Run `method` on `problem`; `PlanInvalidError` (a bug) is not caught."""
    provenance = problem.provenance
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
    )


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
    wanted = {p.stem for p in paths}
    with results_path.open("a", encoding="utf-8", newline="\n") as results:
        for path in paths:
            todo = [m for m in methods if (path.stem, m.value) not in done]
            if not todo:
                continue
            problem = load_scenario(path)
            for method in todo:
                record = run_one(path.stem, problem, method)
                results.write(record.to_json() + "\n")
                results.flush()
                records.append(record)
                if progress is not None:
                    progress(f"{path.stem} {method.value}: {record.status} {record.seconds:.1f}s")
    wanted_methods = {m.value for m in methods}
    return [r for r in records if r.instance in wanted and r.method in wanted_methods]
