from pathlib import Path

import pytest
from builders import at, evolve, make_problem
from test_solve import closed, disrupted_with_gpus

from smartcampus.baselines.sequential import PASSES, pass_settings, sequential
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.generator.scenario import load_scenario
from smartcampus.rules.validator import validate
from smartcampus.solver.solve import SolverSettings, solve

DEMO = Path(__file__).parents[2] / "scenarios" / "dev" / "ac-failure.json"
FAST = SolverSettings(stage_seconds=(5, 5, 5, 5, 5, 5))
TIER = SolverSettings(stage_seconds=(30, 30, 9, 9, 6, 6))


@pytest.mark.parametrize("tier", [SolverSettings(), TIER, FAST])
def test_the_passes_share_the_tiers_total_time(tier: SolverSettings) -> None:
    settings = pass_settings(tier)
    assert sum(sum(s.stage_seconds) for s in settings) == pytest.approx(sum(tier.stage_seconds))
    for spec, s in zip(PASSES, settings, strict=True):
        kept = set(range(6)) - s.skip_stages
        assert kept == set(spec.stages)
        assert all(s.stage_seconds[i] == 0 for i in s.skip_stages)
        assert (s.num_workers, s.random_seed) == (tier.num_workers, tier.random_seed)


def test_each_domain_is_opened_by_its_own_pass_only() -> None:
    rooms, equipment, timing = PASSES
    assert not rooms.moves_allowed and not rooms.start_free and not rooms.only_cancelled
    assert equipment.moves_allowed and not equipment.start_free and equipment.only_cancelled
    assert timing.moves_allowed and timing.start_free and timing.only_cancelled


def test_equipment_moves_are_left_to_the_equipment_pass() -> None:
    problem = disrupted_with_gpus()  # the class needs 3 gpus and its room is closed
    result = sequential(problem, FAST)
    assert validate(problem, result.plan) == []
    assert result.plan.cancelled == frozenset()
    assert [s.name.split(":")[0] for s in result.stages].count("equipment") == 3
    assert result.plan.moves  # pass 1 could not place it; pass 2 brought the gpus


def test_a_problem_with_nothing_to_repair_changes_nothing() -> None:
    problem = make_problem()
    result = sequential(problem, FAST)
    assert result.values.cancellations == 0 and result.values.people_moved == 0


def test_a_room_only_repair_never_uses_the_later_passes() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    result = sequential(problem, FAST)
    assert validate(problem, result.plan) == []
    assert not result.plan.moves
    [assignment] = result.plan.assignments
    assert assignment.start_min == at(1, 10)  # the start stays: only the room changed


@pytest.mark.parametrize("which", ["gpus", "room", "demo"])
def test_joint_is_never_worse_than_sequential(which: str) -> None:
    problems: dict[str, RecoveryProblem] = {
        "gpus": disrupted_with_gpus(),
        "room": evolve(make_problem(), faults=closed("A1")),
        "demo": load_scenario(DEMO),
    }
    problem = problems[which]
    joint = solve(problem, FAST).values
    assert joint <= sequential(problem, FAST).values
