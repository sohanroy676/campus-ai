import shutil
from pathlib import Path

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


def test_compare_runs_every_method_on_one_scenario() -> None:
    result = runner.invoke(app, ["compare", "scenarios/dev/ac-failure.json"])
    assert result.exit_code == 0, result.output
    for method in ("joint", "greedy", "resolve", "sequential"):
        assert method in result.output


def test_compare_rejects_an_unknown_method_and_a_missing_file() -> None:
    bad = runner.invoke(app, ["compare", "scenarios/dev/ac-failure.json", "--methods", "magic"])
    assert bad.exit_code == 2 and "unknown method" in bad.output
    missing = runner.invoke(app, ["compare", "no-such-file.json"])
    assert missing.exit_code == 2


def test_eval_writes_a_report_and_rejects_a_pattern_with_no_match(tmp_path: Path) -> None:
    scenarios = tmp_path / "s"
    scenarios.mkdir()
    shutil.copy("scenarios/dev/ac-failure.json", scenarios / "demo.json")
    out = tmp_path / "out"
    args = ["eval", str(scenarios), "--methods", "greedy,joint", "--out", str(out)]
    ok = runner.invoke(app, args)
    assert ok.exit_code == 0, ok.output
    assert "# Evaluation report" in (out / "report.md").read_text(encoding="utf-8")
    none = runner.invoke(app, [*args, "--pattern", "zzz*.json"])
    assert none.exit_code == 2
    assert runner.invoke(app, ["eval", str(scenarios), "--methods", "x"]).exit_code == 2
