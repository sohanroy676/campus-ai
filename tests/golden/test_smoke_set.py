"""The 20 smoke instances in scenarios/smoke/ (not among the 405) must stay as generated.

Seeds 201 to 220 lie outside the frozen grid (1 to 15) and the pilot seeds (101 to 103). They are
used for the pre-freeze dry run and the greedy-unchanged golden test. Each file is regenerated
from its own provenance and compared byte for byte.
"""

from pathlib import Path

import pytest

from smartcampus.generator.scenario import dump_scenario, load_scenario
from smartcampus.generator.synth import generate_scenario

SMOKE = Path(__file__).parents[2] / "scenarios" / "smoke"

LOAD_SEVERITY_SMALL = [
    (50, "room"),
    (50, "building"),
    (50, "hold"),
    (75, "room"),
    (75, "building"),
    (75, "hold"),
    (90, "room"),
    (90, "building"),
    (90, "hold"),
    (75, "building"),
]
LOAD_SEVERITY_MEDIUM = [
    (50, "room"),
    (50, "hold"),
    (75, "room"),
    (75, "building"),
    (75, "hold"),
    (90, "room"),
    (90, "hold"),
    (50, "building"),
]
SPECS = (
    [("small", load, sev, 201 + i) for i, (load, sev) in enumerate(LOAD_SEVERITY_SMALL)]
    + [("medium", load, sev, 211 + i) for i, (load, sev) in enumerate(LOAD_SEVERITY_MEDIUM)]
    + [("large", 50, "hold", 219), ("large", 75, "room", 220)]
)
EXPECTED = sorted(f"{size}-l{load}-{sev}-s{seed}.json" for size, load, sev, seed in SPECS)


def test_the_smoke_set_is_exactly_twenty_instances_outside_the_grid() -> None:
    assert len(EXPECTED) == 20
    assert sorted(p.name for p in SMOKE.glob("*.json")) == EXPECTED
    assert all(seed > 200 for *_, seed in SPECS)


@pytest.mark.parametrize("name", EXPECTED)
def test_smoke_file_is_reproduced_byte_for_byte(name: str) -> None:
    path = SMOKE / name
    provenance = load_scenario(path).provenance
    assert provenance is not None
    regenerated = generate_scenario(
        provenance.size, provenance.load, provenance.severity, provenance.seed
    )
    assert path.read_bytes() == dump_scenario(regenerated).encode("utf-8")
