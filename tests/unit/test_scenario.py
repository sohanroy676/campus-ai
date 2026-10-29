import json
from pathlib import Path

import pytest
from builders import at, evolve, make_problem

from smartcampus.domain.entities import Fault
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.generator import scenario
from smartcampus.generator.scenario import (
    ScenarioError,
    dump_scenario,
    load_scenario,
    save_scenario,
)


def disrupted() -> RecoveryProblem:
    fault = Fault(
        id="f1", room_id="A1", kind="ac", interval=Interval(start=at(1, 10), end=at(1, 12))
    )
    return evolve(make_problem(), faults=(fault,))


def test_a_saved_scenario_loads_back_equal(tmp_path: Path) -> None:
    problem = disrupted()
    path = tmp_path / "nested" / "s.json"  # the folder is created
    save_scenario(problem, path)
    assert load_scenario(path) == problem


def test_the_dump_is_canonical_text() -> None:
    text = dump_scenario(make_problem())
    assert text.endswith("}\n") and "\r" not in text and text.startswith("{\n  ")
    data = json.loads(text)
    assert data["movable_activity_ids"] == ["act1"]
    assert data["activities"][0]["allowed_room_types"] == ["lab", "lecture"]  # sorted, not hashed


def test_a_missing_file_is_a_scenario_error(tmp_path: Path) -> None:
    with pytest.raises(ScenarioError, match="cannot read file"):
        load_scenario(tmp_path / "nope.json")


def test_a_directory_is_a_scenario_error(tmp_path: Path) -> None:
    with pytest.raises(ScenarioError, match="cannot read file"):
        load_scenario(tmp_path)


def test_a_file_that_is_not_json_is_a_scenario_error(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ScenarioError, match="not a valid scenario"):
        load_scenario(path)


def test_a_file_that_is_not_utf8_is_a_scenario_error(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_bytes(b"\xff\xfe\x00{")
    with pytest.raises(ScenarioError, match="not UTF-8"):
        load_scenario(path)


def test_a_huge_file_is_refused_before_it_is_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "s.json"
    save_scenario(make_problem(), path)
    monkeypatch.setattr(scenario, "MAX_SCENARIO_BYTES", 100)
    with pytest.raises(ScenarioError, match="over the 100 limit"):
        load_scenario(path)


def test_errors_name_the_bad_field(tmp_path: Path) -> None:
    data = json.loads(dump_scenario(make_problem()))
    data["plan_time_min"] = -5
    data["unexpected"] = 1
    path = tmp_path / "s.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ScenarioError) as excinfo:
        load_scenario(path)
    message = str(excinfo.value)
    assert "plan_time_min" in message and "unexpected" in message


def test_a_dangling_reference_is_rejected(tmp_path: Path) -> None:
    data = json.loads(dump_scenario(make_problem()))
    data["movable_activity_ids"] = ["ghost"]
    path = tmp_path / "s.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ScenarioError, match="movable_activity_ids must be activities"):
        load_scenario(path)


def test_a_long_list_of_errors_is_cut_short(tmp_path: Path) -> None:
    data = json.loads(dump_scenario(make_problem()))
    for key in ("campus", "cohorts", "faculty", "activities", "movable_activity_ids", "window"):
        del data[key]
    path = tmp_path / "s.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ScenarioError, match=r"\.\.\. and 1 more"):
        load_scenario(path)


def test_a_top_level_list_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ScenarioError, match="not a valid scenario"):
        load_scenario(path)
