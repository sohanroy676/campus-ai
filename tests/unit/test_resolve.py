from pathlib import Path
from typing import Any

import pytest

from smartcampus.baselines.greedy import greedy
from smartcampus.baselines.resolve import resolve_settings
from smartcampus.coordinator.run import Method, run_scenario
from smartcampus.generator.scenario import load_scenario
from smartcampus.generator.synth import generate_scenario
from smartcampus.sim.store import EventStore
from smartcampus.solver.solve import SolveResult, SolverSettings, solve

DEMO = Path(__file__).parents[2] / "scenarios" / "dev" / "ac-failure.json"
FAST = SolverSettings(stage_seconds=(5, 5, 5, 5, 5, 5))


@pytest.mark.parametrize(
    "tier", [SolverSettings(), SolverSettings(stage_seconds=(30, 30, 9, 9, 6, 6))]
)
def test_resolve_keeps_the_total_budget_and_gives_the_freed_time_to_c_and_k(
    tier: SolverSettings,
) -> None:
    settings = resolve_settings(tier)
    c, p, d, k, s, t = settings.stage_seconds
    freed = sum(tier.stage_seconds[i] for i in (1, 2, 4))
    assert (p, d, s) == (0, 0, 0)
    assert c == tier.stage_seconds[0] + freed / 2
    assert k == tier.stage_seconds[3] + freed / 2
    assert t == tier.stage_seconds[5]
    assert sum(settings.stage_seconds) == sum(tier.stage_seconds)
    assert settings.skip_stages == frozenset({1, 2, 4})
    assert (settings.num_workers, settings.random_seed) == (tier.num_workers, tier.random_seed)


def test_resolve_cancels_no_more_than_joint_and_never_moves_fewer_people() -> None:
    problem = load_scenario(DEMO)
    with EventStore() as joint_store, EventStore() as resolve_store:
        joint = run_scenario(problem, Method.JOINT, joint_store, FAST).values
        resolve = run_scenario(problem, Method.RESOLVE, resolve_store, FAST).values
    # Both minimise C first, so they agree on it. Joint also minimises P, so resolve cannot beat
    # it; resolve minimises K without protecting P, D, S, so it cannot cost more than joint.
    assert resolve.cancellations == joint.cancellations
    assert resolve.people_moved >= joint.people_moved
    assert resolve.cost <= joint.cost


def test_resolve_is_given_the_greedy_start_plan_as_its_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}
    real = solve

    def spy(*args: Any, **kwargs: Any) -> SolveResult:
        seen["hint"] = kwargs.get("hint")
        return real(*args, **kwargs)

    monkeypatch.setattr("smartcampus.baselines.resolve.solve", spy)
    problem = load_scenario(DEMO)
    with EventStore() as store:
        result = run_scenario(problem, Method.RESOLVE, store, FAST)
    assert seen["hint"] == greedy(result.problem, based_on_version=result.log_version - 1)
    assert result.start_plan_seconds <= result.planning_seconds


def test_a_hinted_resolve_never_cancels_more_than_greedy() -> None:
    problem = generate_scenario("small", 75, "building", 1)
    with EventStore() as g_store, EventStore() as r_store:
        g = run_scenario(problem, Method.GREEDY, g_store).values
        r = run_scenario(problem, Method.RESOLVE, r_store, FAST).values
    assert r.cancellations <= g.cancellations
