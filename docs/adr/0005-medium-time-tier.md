# 0005. Separate time tier for medium scenarios

Status: accepted (2026-10-30)

## Context
After two rounds of shrinking the models (ADR 0004), joint with the 10/10/3/3/2/2 s budget returned a plan on 10 of 12 medium scenarios. `medium-l75-hold-s2` and `medium-l75-room-s2` got none: presolve alone takes 2 to 5 s, so the 10 s first stage is too short at this size.

## Decision
- Scenario size picks the time tier (`SolverSettings.for_problem`, from `provenance.size`; no provenance counts as small). Small keeps 10/10/3/3/2/2 s (30 s). Medium and large use 30/30/9/9/6/6 s (90 s). Workers 1, seed 42 in both.
- Callers can still pass explicit settings.
- The 12 medium scenarios move from `scenarios/candidates/medium/` to `scenarios/frozen/` because joint returns a plan on all 12 under this tier.

## Results (joint, medium tier, one clean run each)
All 12 return a plan. Wall time per scenario (greedy start plan included): 7 to 54 s, except `medium-l75-building-s1` (3 m 25 s) and `-building-s2` (2 m 12 s), which also spend most of their time in greedy. `medium-l75-building-s1` ends with 1 cancellation; the other 11 have none.

## Consequences
- Joint times on small and medium are not comparable: report them per tier.
- Large has no measured tier; it reuses the medium budget until it is tested.
- The frozen set is now 24 scenarios; `tests/golden/test_frozen_set.py` regenerates each byte for byte.
