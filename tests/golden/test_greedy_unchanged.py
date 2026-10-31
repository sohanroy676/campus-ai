"""Greedy's plans must not change when its validation is made faster (pre-freeze, item 5).

The golden plans in `data/greedy/` were written by greedy before the R1/R2 speed-up, for the 20
smoke instances in `scenarios/smoke/` and the 9 large-check instances (large, seed 2, loads 50/75/90
x room/building/hold) in `scenarios/frozen/`. A speed-up that changes a violation list or its order
can change which placement greedy accepts; this test shows it did not. The large half takes minutes
and is marked `slow` (it runs in the full suite; `-m "not slow"` leaves it out).

To rewrite the golden files (only when greedy's behaviour is meant to change, with an ADR):
`REGEN_GREEDY_GOLDEN=1 uv run pytest tests/golden/test_greedy_unchanged.py`.
"""

import json
import os
from itertools import product
from pathlib import Path

import pytest

from smartcampus.baselines.greedy import greedy
from smartcampus.domain.plan import Plan
from smartcampus.generator.scenario import load_scenario

ROOT = Path(__file__).parents[2] / "scenarios"
GOLDEN = Path(__file__).parent / "data" / "greedy"

SMOKE = sorted(p.stem for p in (ROOT / "smoke").glob("*.json"))
LARGE_CHECK = [
    f"large-l{load}-{severity}-s2"
    for load, severity in product((50, 75, 90), ("room", "building", "hold"))
]


def canonical(plan: Plan) -> str:
    return json.dumps(
        {
            "assignments": sorted(
                [a.activity_id, a.room_id, a.start_min] for a in plan.assignments
            ),
            "cancelled": sorted(plan.cancelled),
            "moves": sorted(m.model_dump_json() for m in plan.moves),
        },
        sort_keys=True,
    )


def check(path: Path, name: str) -> None:
    plan = greedy(load_scenario(path))
    golden = GOLDEN / f"{name}.json"
    if os.environ.get("REGEN_GREEDY_GOLDEN"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(canonical(plan) + "\n", encoding="utf-8", newline="\n")
        return
    assert canonical(plan) == golden.read_text(encoding="utf-8").strip()


def test_the_smoke_set_is_the_agreed_twenty() -> None:
    assert len(SMOKE) == 20
    sizes = [n.split("-")[0] for n in SMOKE]
    assert (sizes.count("small"), sizes.count("medium"), sizes.count("large")) == (10, 8, 2)


@pytest.mark.parametrize("name", SMOKE)
def test_greedy_plan_on_a_smoke_instance_is_unchanged(name: str) -> None:
    if name.startswith("large-"):
        pytest.skip("large smoke instances run with the slow set")
    check(ROOT / "smoke" / f"{name}.json", name)


@pytest.mark.slow
@pytest.mark.parametrize("name", [n for n in SMOKE if n.startswith("large-")])
def test_greedy_plan_on_a_large_smoke_instance_is_unchanged(name: str) -> None:
    check(ROOT / "smoke" / f"{name}.json", name)


@pytest.mark.slow
@pytest.mark.parametrize("name", LARGE_CHECK)
def test_greedy_plan_on_a_large_check_instance_is_unchanged(name: str) -> None:
    check(ROOT / "frozen" / f"{name}.json", name)
