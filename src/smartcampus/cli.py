"""Typer entry point: generate, run, compare, eval. Commands are stubs until their modules land."""

from pathlib import Path
from typing import Annotated

import typer

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
    method: Annotated[str, typer.Option(help="Recovery method, e.g. joint.")] = "joint",
    report: Annotated[Path | None, typer.Option(help="Where to write the JSON report.")] = None,
) -> None:
    """Run one scenario with one recovery method."""
    _not_implemented("run")


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
