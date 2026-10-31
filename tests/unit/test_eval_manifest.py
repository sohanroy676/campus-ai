import json
import shutil
from pathlib import Path

import pytest

from smartcampus.coordinator.run import Method
from smartcampus.eval.harness import RESULTS_FILE, run_eval, run_one
from smartcampus.eval.manifest import (
    MANIFEST_FILE,
    Environment,
    Manifest,
    check_or_write,
    current_environment,
)
from smartcampus.eval.metrics import RunRecord
from smartcampus.generator.synth import generate_scenario
from smartcampus.solver.solve import NoSolutionError

DEMO = Path(__file__).parents[2] / "scenarios" / "dev" / "ac-failure.json"
ENV = Environment("cpu", "os", "3.12", "9.15", "2.0", "1.15")


def test_the_environment_names_cpu_os_python_and_libraries() -> None:
    env = current_environment()
    assert all(getattr(env, f) for f in ("cpu", "os", "python", "ortools", "numpy", "scipy"))


def test_a_new_run_writes_the_manifest_and_a_resume_accepts_it(tmp_path: Path) -> None:
    first = check_or_write(tmp_path, "abc", ENV)
    assert json.loads((tmp_path / MANIFEST_FILE).read_text(encoding="utf-8"))["commit"] == "abc"
    assert check_or_write(tmp_path, "abc", ENV) == first  # same code and setup: resumed as is


def test_resuming_under_another_commit_or_environment_is_refused(tmp_path: Path) -> None:
    check_or_write(tmp_path, "abc", ENV)
    with pytest.raises(ValueError, match="must not mix"):
        check_or_write(tmp_path, "def", ENV)
    other = Environment("cpu", "os", "3.12", "9.16", "2.0", "1.15")
    with pytest.raises(ValueError, match="must not mix"):
        check_or_write(tmp_path, "abc", other)


def test_records_without_a_manifest_are_refused(tmp_path: Path) -> None:
    (tmp_path / RESULTS_FILE).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"no manifest.json"):
        check_or_write(tmp_path, "abc", ENV)


def test_manifest_round_trips() -> None:
    m = Manifest("abc", ENV, "2026-10-31T00:00:00+00:00")
    assert Manifest.from_json(m.to_json()) == m


def test_run_eval_writes_a_manifest(tmp_path: Path) -> None:
    scenarios = tmp_path / "s"
    scenarios.mkdir()
    shutil.copy(DEMO, scenarios / "demo.json")
    run_eval(scenarios, [Method.GREEDY], tmp_path / "out")
    assert (tmp_path / "out" / MANIFEST_FILE).exists()


def test_greedy_is_its_own_start_and_joint_is_compared_with_it() -> None:
    problem = generate_scenario("small", 50, "room", 1)
    greedy = run_one("s", problem, Method.GREEDY)
    assert greedy.start_unimproved and not greedy.limit_hit
    joint = run_one("s", problem, Method.JOINT, start_values=greedy.values)
    assert joint.values is not None and greedy.values is not None
    assert joint.start_unimproved == (joint.values >= greedy.values)
    assert not run_one("s", problem, Method.JOINT).start_unimproved  # no start values: unknown


def test_a_run_that_stops_at_the_first_stage_limit_is_a_limit_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_plan(*args: object, **kwargs: object) -> None:
        raise NoSolutionError("no solution found within 30 s")

    monkeypatch.setattr("smartcampus.eval.harness.run_scenario", no_plan)
    record = run_one("s", generate_scenario("small", 50, "room", 1), Method.JOINT)
    assert record.limit_hit and not record.start_unimproved


def test_records_from_before_the_flags_load_with_false() -> None:
    line = (
        '{"imputed": {"cancellations": 1, "cost": 0, "delay": 0, "people_moved": 0, '
        '"start_shift": 0, "tie_break": 0}, "instance": "x", "load": 50, "method": "greedy", '
        '"reason": "", "seconds": 1.0, "seed": 1, "severity": "room", "size": "small", '
        '"start_plan_seconds": 0.0, "status": "no_plan", "values": null}'
    )
    record = RunRecord.from_json(line)
    assert not record.limit_hit and not record.start_unimproved


def test_an_interrupted_evaluation_resumes_without_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenarios = tmp_path / "s"
    scenarios.mkdir()
    for name in ("a", "b"):
        shutil.copy(DEMO, scenarios / f"{name}.json")
    out = tmp_path / "out"
    real = run_one
    calls = {"n": 0}

    def killed(*args: object, **kwargs: object) -> RunRecord:
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt  # a kill between two records
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("smartcampus.eval.harness.run_one", killed)
    with pytest.raises(KeyboardInterrupt):
        run_eval(scenarios, [Method.GREEDY], out)
    monkeypatch.setattr("smartcampus.eval.harness.run_one", real)
    records = run_eval(scenarios, [Method.GREEDY], out)
    assert sorted(r.instance for r in records) == ["a", "b"]
    lines = (out / RESULTS_FILE).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
