# Solver and greedy timing runs, 2026-10-30

Raw rows are in `solver-timing-2026-10-30.csv`. These are single runs on one Windows machine with
`num_workers=1`, `random_seed=42`, one timed job at a time. They are measurements for choosing time
tiers, not evaluation results: there is no comparison between methods here.

How a row was made: `run_scenario(problem, JOINT, store, settings)`, so the wall time includes the
greedy start plan. "Presolve" is the time CP-SAT logs as "Starting search at" in the first stage
(it counts against that stage's limit). `no_plan` means joint found no solution within the first
stage's limit (`NoSolutionError`), not that none exists: greedy found a valid plan on every one.

## Medium, load 90 (tier 30/30/9/9/6/6 s, ADR 0005)

Joint returned a plan on all 6, so the combination stays in the frozen set
(`docs/model-spec.md` section 8).

| Scenario | Greedy | Presolve | Wall |
|---|---|---|---|
| room-s1 | 4.8 s | 2.3 s | 36.7 s |
| room-s2 | 7.9 s | 0.9 s | 17.6 s |
| building-s1 | 321.3 s | 1.8 s | 403.4 s |
| building-s2 | 366.7 s | 3.3 s | 460.3 s |
| hold-s1 | 128.9 s | 4.5 s | 224.4 s |
| hold-s2 | 8.7 s | 0.9 s | 18.1 s |

These greedy times were taken before the R1/R2 indexing below. Only `building-s1` was timed again
afterwards.

## Greedy after indexing R1 and R2 `check`

Profile of greedy on `medium-l75-building-s1` (cProfile, so slower than a plain run): 3461
`validate` calls took 233 s; R2 `check` 101 s (all-pairs loop), R1 `check` 74 s (valid starts
recomputed per assignment), R6 18 s, R4 20 s. Both R1 and R2 are now indexed with the same
violations in the same order (`tests/golden/test_r1_r2_check_index.py`).

| Scenario | Before | After |
|---|---|---|
| medium-l90-building-s1 | 321.3 s | 89.5 s |

Still in greedy: `fixed_placements` and `placements` are rebuilt for every rule on every
`validate` call (about 24 s in that profile).

## Large (medium tier reused, seed 1, 3 loads x 3 severities)

| Scenario | Classes | Joint | Greedy | Presolve | Wall |
|---|---|---|---|---|---|
| l50-room | 800 | plan | 0.8 s | 1.6 s | 14.5 s |
| l50-building | 806 | plan | 6.0 s | 7.3 s | 73.1 s |
| l50-hold | 809 | plan | 1.5 s | 1.9 s | 18.0 s |
| l75-room | 1232 | plan | 5.6 s | 2.2 s | 23.0 s |
| l75-building | 1223 | no plan | 42.1 s | 15.3 s | 79.3 s |
| l75-hold | 1255 | plan | 1.5 s | 1.9 s | 14.3 s |
| l90-room | 1443 | no plan | 49.0 s | 15.5 s | 88.9 s |
| l90-building | 1441 | plan | 30.7 s | 2.0 s | 90.1 s |
| l90-hold | 1444 | plan | 3.9 s | 1.7 s | 20.3 s |

Joint returned a plan on 7 of 9. The two failures have a presolve of about 15 s and no solution in
the 30 s first stage, although the greedy plan was passed as a hint (CP-SAT logged the hint as
incomplete). Cause not established. No large tier is chosen and no large scenario is frozen.

## Test suite

801 tests passed in 421 s (about 7 min) after the 270-scenario freeze and the R1/R2 indexing.

## Earlier timing records

Medium candidates before the R6, R4, R5 changes and the medium tier: ADR 0004 and ADR 0005.
