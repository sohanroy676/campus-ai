# 0006. Large time tier and a complete start-plan hint

Status: accepted (2026-10-30)

## Context
- Joint returned no plan on 11 medium scenarios and on 2 of 9 large ones. The solver log on `medium-l90-room-s3` showed why: the hint covered 63,170 of 87,723 variables, CP-SAT could not complete it, and no first solution came in the 30 s first stage although the greedy plan (0 cancelled) was valid. `repair_hint` gave a worse plan (142 cancelled) at 27.8 s. Details: `docs/results/medium-no-plan-diagnosis-2026-10-30.md`.
- Large had no tier of its own and reused the medium budget.

## Decision
- The hint covers every variable. `solve()` solves a copy of the model with the hinted variables fixed (limit 10 s, outside the stage budget) and hints all values from that solution; after each stage the hint is the full solution. The hint still only guides search, so the optimum is unchanged (tests: `test_a_greedy_hint_does_not_change_the_optimum`, `test_a_valid_start_plan_is_hinted_on_every_variable_of_the_model`).
- Large tier: 60/60/18/18/12/12 s (180 s), `SolverSettings.for_problem` from `provenance.size`. Workers 1, seed 42.

## Pilot (joint, greedy hint, one run at a time)
Medium tier (30/30/9/9/6/6 s) against the large tier, with the hint fix in both. Seeds 101 to 103 are pilot seeds, not in the frozen set. Columns: plan?, seconds including greedy, C, P (people moved).

| scenario | medium tier | large tier |
|---|---|---|
| large-l75-building-s1 | plan, 147 s, C 0, P 2070 | plan, 238 s, C 0, P 1499 |
| large-l90-room-s1 | plan, 159 s, C 0, P 2041 | plan, 236 s, C 0, P 1570 |
| large-l75-building-s101 | plan, 124 s, C 0, P 353 | plan, 153 s, C 0, P 353 |
| large-l90-room-s102 | plan, 171 s, C 1, P 402 | plan, 261 s, C 1, P 384 |
| large-l75-hold-s103 | plan, 99 s, C 0, P 0 | plan, 100 s, C 0, P 0 |

Both seed-1 scenarios that had no plan before the hint fix now return one on either tier. The longer tier lowers P on 3 of 5 and changes nothing on the other 2, at about 1.5 to 2 times the wall time. On `large-l90-room-s102` both tiers end with 1 cancellation and every stage at its time limit, so that cancellation is not proven necessary.

## Consequences
- Joint times are not comparable across tiers: report them per size.
- The 135 large scenarios (loads 50/75/90 x room/building/hold x seeds 1 to 15) are frozen, so the frozen set is 405. Any large scenario with no plan is reported as a solver limit.
- Hint completion adds up to 10 s before stage 1 that is not in the stage budget; the eval reports total wall time.
- The plans found on small and medium before this change were found without the complete hint; the 405 are re-run once at the end.
