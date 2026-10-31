"""Typer entry point: generate, run, compare, eval."""

from pathlib import Path
from typing import Annotated

import typer

from smartcampus.coordinator.followups import FollowupError, load_followups
from smartcampus.coordinator.loop import recover
from smartcampus.coordinator.run import Method, run_scenario
from smartcampus.eval.harness import run_eval, run_one
from smartcampus.eval.report import format_report
from smartcampus.generator.scenario import ScenarioError, load_scenario, save_scenario
from smartcampus.generator.synth import GeneratorError, generate_scenario
from smartcampus.reporting.summary import format_cascade, format_summary, write_report
from smartcampus.rules.validator import PlanInvalidError
from smartcampus.sim.state import InvalidEventError
from smartcampus.sim.store import EventStore
from smartcampus.solver.solve import InfeasibleInputError, NoSolutionError

app = typer.Typer(help="Campus disruption recovery: generate, run, compare and evaluate scenarios.")


@app.command()
def generate(
    size: Annotated[str, typer.Option(help="Campus size: small, medium or large.")] = "small",
    load: Annotated[int, typer.Option(help="Timetable load in percent (10 to 95).")] = 75,
    severity: Annotated[str, typer.Option(help="Disruption: room, building or hold.")] = "room",
    seed: Annotated[int, typer.Option(help="Random seed.")] = 1,
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("scenarios/"),
) -> None:
    """Generate a seeded scenario file.

    Exit codes: 0 written; 2 bad options.
    """
    try:
        problem = generate_scenario(size, load, severity, seed)
    except GeneratorError as error:
        typer.echo(f"smartcampus generate: {error}", err=True)
        raise typer.Exit(code=2) from error
    path = out / f"{size}-l{load}-{severity}-s{seed}.json"
    save_scenario(problem, path)
    typer.echo(f"Scenario: {path} ({len(problem.activities)} classes)")


@app.command()
def run(
    scenario: Annotated[Path, typer.Argument(help="Scenario JSON file.")],
    method: Annotated[Method, typer.Option(help="Recovery method.")] = Method.JOINT,
    report: Annotated[Path | None, typer.Option(help="Where to write the JSON report.")] = None,
    db: Annotated[
        Path,
        typer.Option(help="Event log (SQLite). An earlier event log at this path is replaced."),
    ] = Path("var/campus.db"),
) -> None:
    """Run one scenario with one recovery method.

    Exit codes: 0 plan applied; 1 no plan exists; 2 bad scenario file or options; 3 internal error
    (the plan broke a hard rule).
    """
    try:
        problem = load_scenario(scenario)
        with EventStore.create_fresh(db) as store:
            result = run_scenario(problem, method, store)
    except (ScenarioError, InvalidEventError, ValueError) as error:
        typer.echo(f"smartcampus run: {error}", err=True)
        raise typer.Exit(code=2) from error
    except (InfeasibleInputError, NoSolutionError) as error:
        typer.echo(f"smartcampus run: no plan: {error}", err=True)
        raise typer.Exit(code=1) from error
    except PlanInvalidError as error:
        typer.echo(f"smartcampus run: internal error: {error}", err=True)
        raise typer.Exit(code=3) from error
    typer.echo(format_summary(result, scenario, db))
    if report is not None:
        write_report(result, scenario, report)
        typer.echo(f"Report: {report}")


@app.command()
def cascade(
    scenario: Annotated[Path, typer.Argument(help="Scenario JSON file.")],
    followups: Annotated[
        Path | None,
        typer.Option(help="JSON list of later events (e.g. a repair overrun) to re-plan after."),
    ] = None,
    method: Annotated[Method, typer.Option(help="Recovery method.")] = Method.JOINT,
    auto_approve: Annotated[
        bool,
        typer.Option(
            "--auto-approve/--no-auto-approve",
            help="Demo mode: apply plans that fire approval triggers and log it as auto.",
        ),
    ] = True,
    db: Annotated[
        Path,
        typer.Option(help="Event log (SQLite). An earlier event log at this path is replaced."),
    ] = Path("var/campus.db"),
) -> None:
    """Run a scenario, then re-plan after each later event.

    Exit codes: 0 done (a plan may still be waiting for approval); 1 no plan exists; 2 bad
    scenario, follow-up file or options; 3 internal error (a plan broke a hard rule).
    """
    try:
        problem = load_scenario(scenario)
        later = load_followups(followups) if followups is not None else []
        with EventStore.create_fresh(db) as store:
            rounds = recover(problem, store, method, later, auto_approve=auto_approve)
    except (ScenarioError, FollowupError, InvalidEventError, ValueError) as error:
        typer.echo(f"smartcampus cascade: {error}", err=True)
        raise typer.Exit(code=2) from error
    except (InfeasibleInputError, NoSolutionError) as error:
        typer.echo(f"smartcampus cascade: no plan: {error}", err=True)
        raise typer.Exit(code=1) from error
    except PlanInvalidError as error:
        typer.echo(f"smartcampus cascade: internal error: {error}", err=True)
        raise typer.Exit(code=3) from error
    typer.echo(format_cascade(rounds, scenario, followups, db))


def _parse_methods(text: str) -> list[Method]:
    if text == "all":
        return list(Method)
    try:
        return [Method(name.strip()) for name in text.split(",") if name.strip()]
    except ValueError as error:
        names = ", ".join(m.value for m in Method)
        raise ValueError(f"unknown method in {text!r}; choose from: {names} or all") from error


@app.command()
def compare(
    scenario: Annotated[Path, typer.Argument(help="Scenario JSON file.")],
    methods: Annotated[str, typer.Option(help="Methods to run, or 'all'.")] = "all",
) -> None:
    """Compare methods on one scenario: the six stage values and the planning time of each.

    Exit codes: 0 done (a method without a plan is shown as such); 2 bad scenario or options;
    3 internal error (a plan broke a hard rule).
    """
    try:
        problem = load_scenario(scenario)
        chosen = _parse_methods(methods)
        records = [run_one(scenario.stem, problem, method) for method in chosen]
    except (ScenarioError, InvalidEventError, ValueError) as error:
        typer.echo(f"smartcampus compare: {error}", err=True)
        raise typer.Exit(code=2) from error
    except PlanInvalidError as error:
        typer.echo(f"smartcampus compare: internal error: {error}", err=True)
        raise typer.Exit(code=3) from error
    typer.echo(f"{scenario}: {len(problem.movable_activity_ids)} class(es) to recover")
    typer.echo("method      C  P  D  K  S  T   seconds")
    for r in records:
        if r.values is None:
            typer.echo(f"{r.method:<11} no plan ({r.reason})")
            continue
        v = r.values
        typer.echo(
            f"{r.method:<11} {v.cancellations} {v.people_moved} {v.delay} {v.cost} "
            f"{v.start_shift} {v.tie_break}   {r.seconds:.1f}"
        )


@app.command(name="eval")
def eval_(
    scenarios: Annotated[Path, typer.Argument(help="Directory of frozen scenarios.")],
    methods: Annotated[str, typer.Option(help="Methods to run, or 'all'.")] = "all",
    out: Annotated[Path, typer.Option(help="Results directory.")] = Path("results/"),
    pattern: Annotated[str, typer.Option(help="Which scenario files to run.")] = "*.json",
) -> None:
    """Evaluate methods on a scenario set; results.jsonl and report.md go to --out.

    An interrupted evaluation resumes: runs already in results.jsonl are not repeated.

    Exit codes: 0 done; 2 bad directory, pattern or options; 3 internal error.
    """
    try:
        chosen = _parse_methods(methods)
        records = run_eval(scenarios, chosen, out, pattern=pattern, progress=typer.echo)
    except (ScenarioError, InvalidEventError, ValueError) as error:
        typer.echo(f"smartcampus eval: {error}", err=True)
        raise typer.Exit(code=2) from error
    except PlanInvalidError as error:
        typer.echo(f"smartcampus eval: internal error: {error}", err=True)
        raise typer.Exit(code=3) from error
    report = out / "report.md"
    report.write_text(format_report(records), encoding="utf-8", newline="\n")
    typer.echo(f"{len(records)} run(s); report: {report}")
