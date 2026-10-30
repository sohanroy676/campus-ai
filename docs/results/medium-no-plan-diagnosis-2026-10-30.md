# Medium no-plans: diagnosis and fix (2026-10-30)

Question: why did joint return no plan on 11 medium scenarios (`docs/results/frozen-joint-check-2026-10-30.md`), and is it a defect or search difficulty?

## Method
`medium-l90-room-s3`, greedy start plan as hint, medium tier (stage 1 = 30 s), `num_workers=1`, `random_seed=42`, CP-SAT search log on. One scenario at a time, nothing else running. Scratch scripts were in the session scratchpad (not in the repo).

## Finding: hint defect, not search difficulty
- Greedy found a plan with 0 cancelled, 155 assigned (8.7 s). Stage 1 minimises cancellations, so the hint was already optimal for stage 1.
- The log said `The solution hint is incomplete: 63170 out of 87723 non fixed variables hinted` (32,982 of 47,735 after presolve). `solve()` hinted only the decision variables (options, cancelled, units, moved, move start). The helper literals added by the rules and the objective were left out.
- CP-SAT could not finish the hint: `Starting subsolver 'main' hint search at 14.95s`, no solution by 30 s, 0 conflicts, status UNKNOWN. That is the `NoSolutionError`. Presolve took 12.3 s of the 30 s.
- Setting `repair_hint=True` did not help: a first solution at 27.8 s with 142 cancellations, far worse than the 0 of the start plan.

## Fix (same semantics: the hint only guides search)
`solver/solve.py` `_complete_hint`: clone the model, fix the hinted variables (`fix_variables_to_their_hinted_value`), solve the copy (limit 10 s, outside the stage budget), and hint every variable of the model from that solution. After each stage the hint is also the full solution, not just the decision variables. If the copy has no solution, the partial hint is kept.

After the fix the log says `The solution hint is complete and is feasible`, and stage 1 has a solution with value 0 at 11.5 s (presolve included).

## Re-run of the 11 former no-plans (medium tier, default settings, greedy hint)
Seconds include the greedy run. Columns: C, P, D, K, S, T as in the run report.

| scenario | result | s | C | P | D | K | S | T |
|---|---|---|---|---|---|---|---|---|
| medium-l75-building-s15 | plan | 120.3 | 0 | 276 | 2400 | 0 | 2430 | 10133 |
| medium-l75-hold-s15 | plan | 84.8 | 0 | 58 | 0 | 0 | 60 | 1017 |
| medium-l75-hold-s6 | plan | 54.1 | 0 | 53 | 0 | 0 | 0 | 2021 |
| medium-l75-room-s13 | plan | 57.3 | 0 | 88 | 0 | 0 | 0 | 3061 |
| medium-l75-room-s7 | plan | 70.4 | 0 | 61 | 30 | 0 | 360 | 1031 |
| medium-l90-hold-s10 | plan | 100.7 | 0 | 1732 | 540 | 0 | 990 | 22527 |
| medium-l90-hold-s5 | plan | 113.2 | 0 | 1605 | 1230 | 0 | 1470 | 19500 |
| medium-l90-hold-s9 | plan | 101.9 | 0 | 1708 | 720 | 0 | 1350 | 22475 |
| medium-l90-room-s10 | plan | 108.8 | 0 | 3622 | 1620 | 0 | 3240 | 51790 |
| medium-l90-room-s3 | plan | 105.2 | 0 | 147 | 600 | 0 | 690 | 5085 |
| medium-l90-room-s8 | plan | 112.0 | 0 | 1954 | 1110 | 0 | 2340 | 20555 |

All 11 return a plan; none needed a longer tier, so the medium tier stays 30/30/9/9/6/6 s. Raw rows: `medium-no-plan-rerun-2026-10-30.csv`.

## Still to do
- Re-run all 405 once at the end (planned with the eval harness); the other 229 medium and small plans were found without this fix and will be re-measured then, so their times may change.
- Apply the fix to the large failures (`large-l75-building-s1`, `large-l90-room-s1`) before choosing a large tier (item b).
- The hint completion adds time before stage 1 that is not in the stage budget; the eval reports total wall time.
