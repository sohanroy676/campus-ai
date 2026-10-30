"""Time tier chosen by scenario size."""

import pytest
from builders import make_problem

from smartcampus.generator.synth import generate_scenario
from smartcampus.solver.solve import MEDIUM_STAGE_SECONDS, SolverSettings


def test_problem_without_provenance_gets_the_small_tier() -> None:
    assert SolverSettings.for_problem(make_problem()) == SolverSettings()


@pytest.mark.parametrize(("size", "medium"), [("small", False), ("medium", True)])
def test_tier_follows_provenance_size(size: str, medium: bool) -> None:
    settings = SolverSettings.for_problem(generate_scenario(size, 50, "room", 1))
    assert (settings.stage_seconds == MEDIUM_STAGE_SECONDS) is medium
    assert settings.num_workers == 1
    assert settings.random_seed == 42


def test_medium_tier_is_three_times_small() -> None:
    assert tuple(3.0 * s for s in SolverSettings().stage_seconds) == MEDIUM_STAGE_SECONDS
