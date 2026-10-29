import json
from pathlib import Path

import pytest
from builders import at, evolve, make_activity, make_problem
from typer.testing import CliRunner, Result

from smartcampus.cli import app
from smartcampus.domain.entities import Fault
from smartcampus.domain.time import Interval
from smartcampus.generator.scenario import dump_scenario, save_scenario
from smartcampus.rules.base import RuleId, Violation
from smartcampus.rules.validator import PlanInvalidError
from smartcampus.solver.solve import NoSolutionError

runner = CliRunner()
DEMO = Path(__file__).parents[2] / "scenarios" / "dev" / "ac-failure.json"
MORNING = Interval(start=at(1, 8), end=at(1, 12))


def run(*args: str | Path) -> Result:
    return runner.invoke(app, ["run", *map(str, args)])


def test_help_lists_the_methods_and_exit_codes() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "joint" in result.output and "greedy" in result.output
    assert "Exit codes" in result.output.replace("\n", " ") or "exit codes" in result.output.lower()


@pytest.mark.parametrize("method", ["joint", "greedy"])
def test_the_demo_scenario_runs_end_to_end(method: str, tmp_path: Path) -> None:
    db = tmp_path / "var" / "campus.db"
    result = run(DEMO, "--method", method, "--db", db)
    assert result.exit_code == 0, result.output
    out = result.output
    assert f"Method:     {method}" in out
    assert "ml-lab: AI-Lab-01 Tue 10:00 -> AI-Lab-02" in out
    assert "Hard rules R1-R8: all satisfied" in out
    assert "2 event(s)" in out
    assert db.is_file()


def test_the_default_method_is_joint(tmp_path: Path) -> None:
    result = run(DEMO, "--db", tmp_path / "c.db")
    assert result.exit_code == 0 and "Method:     joint" in result.output


def test_the_report_is_written_and_a_rerun_gives_the_same_bytes(tmp_path: Path) -> None:
    reports = []
    for n in range(2):
        path = tmp_path / f"r{n}.json"
        result = run(DEMO, "--db", tmp_path / "c.db", "--report", path)
        assert result.exit_code == 0
        reports.append(path.read_bytes())
    assert reports[0] == reports[1]
    assert json.loads(reports[0])["stage_values"]["cancellations"] == 0


def test_running_again_replaces_the_event_log(tmp_path: Path) -> None:
    db = tmp_path / "c.db"
    for _ in range(2):
        result = run(DEMO, "--db", db, "--method", "greedy")
        assert "2 event(s)" in result.output


def test_a_missing_scenario_exits_2(tmp_path: Path) -> None:
    result = run(tmp_path / "nope.json", "--db", tmp_path / "c.db")
    assert result.exit_code == 2
    assert "cannot read file" in result.output
    assert not (tmp_path / "c.db").exists()  # nothing was started


def test_a_broken_scenario_exits_2_naming_the_field(tmp_path: Path) -> None:
    data = json.loads(dump_scenario(make_problem()))
    data["plan_time_min"] = -1
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    result = run(bad, "--db", tmp_path / "c.db")
    assert result.exit_code == 2 and "plan_time_min" in result.output


def test_an_unknown_method_exits_2(tmp_path: Path) -> None:
    result = run(DEMO, "--method", "magic", "--db", tmp_path / "c.db")
    assert result.exit_code == 2


def test_a_db_path_that_is_another_file_is_not_overwritten(tmp_path: Path) -> None:
    precious = tmp_path / "notes.txt"
    precious.write_text("keep me", encoding="utf-8")
    result = run(DEMO, "--db", precious)
    assert result.exit_code == 2 and "not an event store" in result.output
    assert precious.read_text(encoding="utf-8") == "keep me"


def test_a_repeated_fault_id_exits_2(tmp_path: Path) -> None:
    fault = Fault(id="same", room_id="A1", kind="ac", interval=MORNING)
    path = tmp_path / "dup.json"
    save_scenario(evolve(make_problem(), faults=(fault, fault)), path)
    result = run(path, "--db", tmp_path / "c.db")
    assert result.exit_code == 2 and "already occurred" in result.output


@pytest.mark.parametrize("method", ["joint", "greedy"])
def test_input_that_breaks_a_rule_has_no_plan_and_exits_1(method: str, tmp_path: Path) -> None:
    clash = make_problem(
        activities=(
            make_activity(),
            make_activity(
                id="x", cohort_id="c2", faculty_ids=("f2",), room_id="A2", start_min=at(1, 12)
            ),
            make_activity(
                id="y", cohort_id="c1", faculty_ids=("f1",), room_id="A2", start_min=at(1, 12)
            ),
        ),
    )
    path = tmp_path / "clash.json"
    save_scenario(clash, path)
    result = run(path, "--method", method, "--db", tmp_path / "c.db")
    assert result.exit_code == 1
    assert "no plan" in result.output and "R2" in result.output


def test_a_plan_that_breaks_a_rule_is_an_internal_error_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object, **__: object) -> None:
        raise PlanInvalidError([Violation(RuleId.R2, "two classes in one room", ("a", "b"))])

    monkeypatch.setattr("smartcampus.cli.run_scenario", broken)
    result = run(DEMO, "--db", tmp_path / "c.db")
    assert result.exit_code == 3
    assert "internal error" in result.output and "R2" in result.output


def test_a_solver_that_finds_nothing_in_time_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def too_slow(*_: object, **__: object) -> None:
        raise NoSolutionError("no solution found within 10 s")

    monkeypatch.setattr("smartcampus.cli.run_scenario", too_slow)
    result = run(DEMO, "--db", tmp_path / "c.db")
    assert result.exit_code == 1 and "no solution found within 10 s" in result.output
