"""Typer entry point: generate, run, compare, eval. Commands are stubs until their modules land."""

from pathlib import Path
from typing import Annotated

import typer

from smartcampus.coordinator.run import Method, run_scenario
from smartcampus.generator.scenario import ScenarioError, load_scenario
from smartcampus.reporting.summary import format_summary, write_report
from smartcampus.rules.validator import PlanInvalidError
from smartcampus.sim.state import InvalidEventError
from smartcampus.sim.store import EventStore
from smartcampus.solver.solve import InfeasibleInputError, NoSolutionError

app = typer.Typer(help="Campus disruption recovery: generate, run, compare and evaluate scenarios.")


def _not_implemented(command: str) -> None:
    typer.echo(f"smartcampus {command}: not implemented yet", err=True)
    raise typer.Exit(code=1)


@app.command()
def generate(
    size: Annotated[str, typer.Option(help="Campus size: small, medium or large.")] = "small",
    load: Annotated[int, typer.Option(help="Timetable load in percent.")] = 75,
    severity: Annotated[str, typer.Option(help="Disruption severity, e.g. room.")] = "room",
    seed: Annotated[int, typer.Option(help="Random seed.")] = 1,
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("scenarios/"),
) -> None:
    """Generate a seeded scenario file."""
    _not_implemented("generate")


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
def compare(
    scenario: Annotated[Path, typer.Argument(help="Scenario JSON file.")],
) -> None:
    """Compare all methods on one scenario."""
    _not_implemented("compare")


@app.command(name="eval")
def eval_(
    scenarios: Annotated[Path, typer.Argument(help="Directory of frozen scenarios.")],
    methods: Annotated[str, typer.Option(help="Methods to run, or 'all'.")] = "all",
    out: Annotated[Path, typer.Option(help="Results directory.")] = Path("results/"),
) -> None:
    """Evaluate methods on a frozen scenario set."""
    _not_implemented("eval")
