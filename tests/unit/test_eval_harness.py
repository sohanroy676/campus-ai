import re
import shutil
from pathlib import Path

import pytest

from smartcampus.coordinator.run import Method
from smartcampus.eval.harness import RESULTS_FILE, code_version, read_results, run_eval, run_one
from smartcampus.eval.metrics import NO_PLAN, PLAN, RunRecord, cancel_everything_values
from smartcampus.eval.report import format_report
from smartcampus.generator.scenario import load_scenario
from smartcampus.generator.synth import GENERATOR_VERSION, generate_scenario
from smartcampus.solver.solve import NoSolutionError, SolverSettings

DEMO = Path(__file__).parents[2] / "scenarios" / "dev" / "ac-failure.json"


@pytest.fixture
def scenarios(tmp_path: Path) -> Path:
    directory = tmp_path / "scenarios"
    directory.mkdir()
    shutil.copy(DEMO, directory / "demo.json")
    return directory


def test_one_run_records_the_plan_values_and_times() -> None:
    problem = load_scenario(DEMO)
    record = run_one("demo", problem, Method.JOINT)
    assert record.status == PLAN and record.values is not None and record.solved
    assert record.method == "joint" and record.instance == "demo"
    # joint includes its greedy start plan (the clock is coarse on Windows, so it may read 0)
    assert 0 <= record.start_plan_seconds <= record.seconds
    assert run_one("demo", problem, Method.GREEDY).start_plan_seconds == 0.0


def test_the_cancel_everything_score_is_the_worst_case() -> None:
    problem = load_scenario(DEMO)
    imputed = cancel_everything_values(problem)
    assert imputed.cancellations == len(problem.movable_activity_ids)
    record = run_one("demo", problem, Method.JOINT)
    assert record.values is not None and record.values <= imputed


def test_a_method_without_a_plan_is_recorded_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = load_scenario(DEMO)

    def no_plan(*args: object, **kwargs: object) -> None:
        raise NoSolutionError("no solution found within 30 s")

    monkeypatch.setattr("smartcampus.eval.harness.run_scenario", no_plan)
    record = run_one("demo", problem, Method.JOINT)
    assert record.status == NO_PLAN and record.values is None and not record.solved
    assert "NoSolutionError" in record.reason
    assert record.effective_values() == cancel_everything_values(problem)


def test_a_run_writes_results_and_resumes_without_repeating(
    scenarios: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    methods = [Method.GREEDY, Method.RESOLVE]
    first = run_eval(scenarios, methods, out)
    assert sorted(r.method for r in first) == ["greedy", "resolve"]
    lines = (out / RESULTS_FILE).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    seen: list[str] = []
    again = run_eval(scenarios, methods, out, progress=seen.append)
    assert seen == []  # nothing was run again
    assert len((out / RESULTS_FILE).read_text(encoding="utf-8").splitlines()) == 2
    assert sorted(r.method for r in again) == ["greedy", "resolve"]
    # a new method runs on its own and keeps the earlier records
    more = run_eval(scenarios, [*methods, Method.SEQUENTIAL], out, progress=seen.append)
    assert len(seen) == 1 and len(more) == 3 and len(read_results(out / RESULTS_FILE)) == 3


def test_only_the_requested_methods_and_scenarios_are_returned(
    scenarios: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    run_eval(scenarios, [Method.GREEDY, Method.RESOLVE], out)
    only_greedy = run_eval(scenarios, [Method.GREEDY], out)
    assert [r.method for r in only_greedy] == ["greedy"]


def test_a_pattern_that_matches_nothing_is_an_error(scenarios: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no scenarios match"):
        run_eval(scenarios, [Method.GREEDY], tmp_path / "out", pattern="nothing-*.json")


def test_the_report_has_every_section_for_all_methods(scenarios: Path, tmp_path: Path) -> None:
    records = run_eval(scenarios, list(Method), tmp_path / "out")
    report = format_report(records)
    for text in (
        "Plan rate",
        "Median (IQR)",
        "greedy start plan",
        "joint against each comparator",
        "Sensitivity",
        "Threats to validity",
        "| joint vs greedy |",
        "| joint vs resolve |",
        "| joint vs sequential |",
    ):
        assert text in report


def test_settings_stay_deterministic() -> None:
    assert SolverSettings().num_workers == 1 and SolverSettings().random_seed == 42


def test_a_record_carries_the_code_version_settings_and_generator_version() -> None:
    problem = generate_scenario("small", 50, "room", 1)
    joint = run_one("s", problem, Method.JOINT, commit="abc123")
    assert joint.commit == "abc123" and joint.generator_version == GENERATOR_VERSION
    assert joint.stage_seconds == list(SolverSettings().stage_seconds)
    assert (joint.num_workers, joint.random_seed) == (1, 42)
    greedy_record = run_one("s", problem, Method.GREEDY)
    assert greedy_record.stage_seconds == [] and greedy_record.num_workers == 0
    resolve = run_one("s", problem, Method.RESOLVE)
    assert resolve.stage_seconds != joint.stage_seconds  # the dropped stages' time was moved


def test_a_run_without_a_plan_still_names_its_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_plan(*args: object, **kwargs: object) -> None:
        raise NoSolutionError("no solution found within 30 s")

    monkeypatch.setattr("smartcampus.eval.harness.run_scenario", no_plan)
    record = run_one("s", generate_scenario("small", 50, "room", 1), Method.JOINT, commit="c")
    assert record.status == NO_PLAN and record.commit == "c"
    assert record.stage_seconds == list(SolverSettings().stage_seconds)


def test_run_eval_stamps_every_record_with_the_current_commit(
    scenarios: Path, tmp_path: Path
) -> None:
    records = run_eval(scenarios, [Method.GREEDY], tmp_path / "out")
    assert {r.commit for r in records} == {code_version()}
    assert read_results(tmp_path / "out" / RESULTS_FILE)[0].commit == code_version()


def test_code_version_names_a_commit_and_marks_a_dirty_tree() -> None:
    version = code_version()
    assert version == "unknown" or re.fullmatch(r"[0-9a-f]{40}(\+dirty)?", version)


def test_older_records_without_stamps_still_load() -> None:
    line = (
        '{"imputed": {"cancellations": 1, "cost": 0, "delay": 0, "people_moved": 0, '
        '"start_shift": 0, "tie_break": 0}, "instance": "x", "load": 50, "method": "greedy", '
        '"reason": "", "seconds": 1.0, "seed": 1, "severity": "room", "size": "small", '
        '"start_plan_seconds": 0.0, "status": "no_plan", "values": null}'
    )
    record = RunRecord.from_json(line)
    assert record.commit == "" and record.stage_seconds == [] and record.num_workers == 0


def test_the_report_names_the_code_and_warns_about_mixed_versions(tmp_path: Path) -> None:
    problem = generate_scenario("small", 50, "room", 1)
    a = run_one("s1", problem, Method.GREEDY, commit="a" * 40)
    b = run_one("s2", problem, Method.GREEDY, commit="b" * 40 + "+dirty")
    single = format_report([a])
    assert "Code: aaaaaaaaaaaa" in single and "WARNING" not in single
    mixed = format_report([a, b])
    assert "bbbbbbbbbbbb+dirty" in mixed and "WARNING: records come from 2 code version" in mixed
    unstamped = format_report([a, run_one("s3", problem, Method.GREEDY)])
    assert "1 run(s) carry no commit" in unstamped
