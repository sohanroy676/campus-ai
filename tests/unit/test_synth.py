import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from smartcampus.cli import app
from smartcampus.coordinator.run import Method, run_scenario
from smartcampus.domain.plan import Plan
from smartcampus.domain.time import SLOTS_PER_WEEK
from smartcampus.generator.scenario import dump_scenario, load_scenario
from smartcampus.generator.synth import (
    GENERATOR_VERSION,
    SEVERITIES,
    GeneratorError,
    generate_scenario,
)
from smartcampus.reporting.summary import report_dict
from smartcampus.rules.validator import validate
from smartcampus.sim.store import EventStore
from smartcampus.solver.solve import SolverSettings

runner = CliRunner()
FAST = SolverSettings(stage_seconds=(5, 5, 3, 3, 2, 2), num_workers=1, random_seed=42)


def test_the_same_parameters_give_the_same_file() -> None:
    first = generate_scenario("small", 75, "room", 7)
    second = generate_scenario("small", 75, "room", 7)
    assert dump_scenario(first) == dump_scenario(second)


def test_another_seed_gives_another_scenario() -> None:
    texts = {dump_scenario(generate_scenario("small", 50, "room", s)) for s in range(4)}
    assert len(texts) == 4


def test_provenance_records_the_parameters_and_the_generator_version() -> None:
    problem = generate_scenario("small", 50, "building", 3)
    assert problem.provenance is not None
    assert problem.provenance.model_dump() == {
        "generator_version": GENERATOR_VERSION,
        "seed": 3,
        "size": "small",
        "load": 50,
        "severity": "building",
    }


@pytest.mark.parametrize(("size", "rooms"), [("small", 8), ("medium", 21), ("large", 40)])
def test_campus_size_tiers(size: str, rooms: int) -> None:
    problem = generate_scenario(size, 50, "room", 1)
    assert len(problem.campus.rooms) == rooms


@pytest.mark.parametrize("load", [10, 50, 75, 90])
def test_the_timetable_reaches_the_target_load(load: int) -> None:
    problem = generate_scenario("small", load, "room", 1)
    used = sum(a.duration_slots for a in problem.activities)
    share = 100 * used / (len(problem.campus.rooms) * SLOTS_PER_WEEK)
    assert load - 8 <= share <= load + 2  # a dense week may fall a little short of the target


def test_a_room_fault_hits_one_room_and_a_building_fault_hits_the_whole_building() -> None:
    room = generate_scenario("small", 50, "room", 1)
    building = generate_scenario("small", 50, "building", 1)
    assert len(room.faults) == 1 and not room.holds
    rooms_in = {f.room_id for f in building.faults}
    buildings = {building.campus.room(r).building_id for r in rooms_in}
    assert len(buildings) == 1
    assert len(rooms_in) == sum(1 for r in building.campus.rooms if r.building_id in buildings)


def test_a_hold_scenario_has_a_hold_and_no_fault() -> None:
    problem = generate_scenario("small", 50, "hold", 1)
    assert len(problem.holds) == 1 and not problem.faults


def test_the_fault_starts_after_plan_time_and_hits_a_class() -> None:
    problem = generate_scenario("small", 75, "room", 5)
    [fault] = problem.faults
    assert fault.interval.start >= problem.plan_time_min
    assert any(
        a.room_id == fault.room_id
        and a.start_min < fault.interval.end
        and fault.interval.start < a.start_min + a.duration_min
        for a in problem.activities
    )
    assert problem.movable_activity_ids


@pytest.mark.parametrize("severity", SEVERITIES)
def test_cancelling_every_movable_class_is_a_valid_plan(severity: str) -> None:
    problem = generate_scenario("small", 90, severity, 2)
    plan = Plan(based_on_version=0, assignments=(), cancelled=problem.movable_activity_ids)
    assert validate(problem, plan) == []


@pytest.mark.parametrize(
    ("size", "load", "severity"),
    [("tiny", 50, "room"), ("small", 5, "room"), ("small", 99, "room"), ("small", 50, "flood")],
)
def test_bad_parameters_are_rejected(size: str, load: int, severity: str) -> None:
    with pytest.raises(GeneratorError):
        generate_scenario(size, load, severity, 1)


def test_a_generated_file_loads_back_unchanged(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["generate", "--size", "small", "--load", "50", "--seed", "4", "--out", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    path = tmp_path / "small-l50-room-s4.json"
    assert load_scenario(path) == generate_scenario("small", 50, "room", 4)
    assert path.read_text(encoding="utf-8") == dump_scenario(
        generate_scenario("small", 50, "room", 4)
    )
    assert "\r" not in path.read_text(encoding="utf-8")


def test_the_cli_rejects_bad_options(tmp_path: Path) -> None:
    result = runner.invoke(app, ["generate", "--size", "huge", "--out", str(tmp_path)])
    assert result.exit_code == 2
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("method", list(Method))
@pytest.mark.parametrize("severity", SEVERITIES)
def test_a_generated_scenario_is_solved_by_both_methods(method: Method, severity: str) -> None:
    problem = generate_scenario("small", 50, severity, 1)
    with EventStore() as store:
        result = run_scenario(problem, method, store, FAST)
    assert validate(result.problem, result.plan) == []


def test_the_run_report_carries_the_provenance() -> None:
    problem = generate_scenario("small", 50, "building", 1)
    with EventStore() as store:
        result = run_scenario(problem, Method.GREEDY, store, FAST)
    report = report_dict(result, Path("x.json"))
    assert json.loads(json.dumps(report))["provenance"]["generator_version"] == GENERATOR_VERSION
    assert report["provenance"]["seed"] == 1
