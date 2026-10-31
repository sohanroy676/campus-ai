"""Time tier chosen by scenario size."""

import pytest
from builders import make_problem

from smartcampus.generator.synth import generate_scenario
from smartcampus.solver.solve import LARGE_STAGE_SECONDS, MEDIUM_STAGE_SECONDS, SolverSettings


def test_problem_without_provenance_gets_the_small_tier() -> None:
    assert SolverSettings.for_problem(make_problem()) == SolverSettings()


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ("small", SolverSettings().stage_seconds),
        ("medium", MEDIUM_STAGE_SECONDS),
        ("large", LARGE_STAGE_SECONDS),
    ],
)
def test_tier_follows_provenance_size(size: str, expected: tuple[float, ...]) -> None:
    settings = SolverSettings.for_problem(generate_scenario(size, 50, "room", 1))
    assert settings.stage_seconds == expected
    assert settings.num_workers == 1
    assert settings.random_seed == 42


def test_medium_tier_is_three_times_small_and_large_six_times() -> None:
    small = SolverSettings().stage_seconds
    assert tuple(3.0 * s for s in small) == MEDIUM_STAGE_SECONDS
    assert tuple(6.0 * s for s in small) == LARGE_STAGE_SECONDS
