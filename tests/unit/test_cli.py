import pytest
from typer.testing import CliRunner

import smartcampus
from smartcampus.cli import app

runner = CliRunner()


def test_package_exposes_version() -> None:
    assert smartcampus.__version__ == "0.1.0"


def test_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("generate", "run", "compare", "eval"):
        assert command in result.output


@pytest.mark.parametrize(
    "args",
    [["generate"], ["run", "x.json"], ["compare", "x.json"], ["eval", "scenarios/frozen/"]],
)
def test_stub_commands_fail_loudly(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert "not implemented yet" in result.output
