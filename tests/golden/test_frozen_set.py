"""The frozen evaluation set in scenarios/frozen/ must stay exactly what the generator makes.

Each file is regenerated from its own provenance and compared byte for byte. If one of these
fails, either the generator changed its output for a seed (bump GENERATOR_VERSION and write a new
set; never edit files in scenarios/frozen/) or a frozen file was edited by hand.
"""

from itertools import product
from pathlib import Path

import pytest

from smartcampus.generator.scenario import dump_scenario, load_scenario
from smartcampus.generator.synth import GENERATOR_VERSION, generate_scenario

FROZEN = Path(__file__).parents[2] / "scenarios" / "frozen"

SIZES = ("small", "medium")
LOADS = (50, 75, 90)
SEVERITIES = ("room", "building", "hold")
SEEDS = tuple(range(1, 16))  # large joins when its time tier is measured (135 per size)

EXPECTED = sorted(
    f"{size}-l{load}-{severity}-s{seed}.json"
    for size, load, severity, seed in product(SIZES, LOADS, SEVERITIES, SEEDS)
)


def test_frozen_set_holds_exactly_the_agreed_grid() -> None:
    assert sorted(p.name for p in FROZEN.glob("*.json")) == EXPECTED


@pytest.mark.parametrize("name", EXPECTED)
def test_frozen_file_is_reproduced_byte_for_byte(name: str) -> None:
    path = FROZEN / name
    provenance = load_scenario(path).provenance
    assert provenance is not None
    assert provenance.generator_version == GENERATOR_VERSION
    assert name == (
        f"{provenance.size}-l{provenance.load}-{provenance.severity}-s{provenance.seed}.json"
    )
    regenerated = generate_scenario(
        provenance.size, provenance.load, provenance.severity, provenance.seed
    )
    assert path.read_bytes() == dump_scenario(regenerated).encode("utf-8")
