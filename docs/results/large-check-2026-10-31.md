# Large one-seed-per-cell check, 2026-10-31

Not a result of the evaluation: a cheap check before the freeze. Code at 7936f28 (clean tree), `num_workers=1`, `random_seed=42`, large tier 60/60/18/18/12/12 s. Instances: `large-l{50,75,90}-{room,building,hold}-s2` (9). Greedy and joint on all 9; resolve, sequential and contract_net on the 3 load-90 instances. Data: `large-check-2026-10-31.csv`. Job 2 was killed once by the system for low memory and resumed from `results.jsonl` (only the two missing runs were re-run).

## Plan rate
- Greedy and joint returned a plan on 9 of 9. Resolve, sequential and contract_net returned a status `plan` on 3 of 3. No large no-plan for joint, so no new large tier is needed for joint.
- Status `plan` is not the same as a usable plan, see resolve below.

## Joint and greedy (cancellations C, people moved P, seconds)
| Instance | greedy | joint |
|---|---|---|
| l50-building | C0 P1007 10.2 s | C0 P516 152.5 s |
| l50-hold | C0 P17 2.6 s | C0 P17 65.6 s |
| l50-room | C0 P172 2.7 s | C0 P46 46.2 s |
| l75-building | C2 P2391 36.0 s | C1 P1340 223.2 s |
| l75-hold | C0 P74 6.3 s | C0 P70 164.5 s |
| l75-room | C0 P67 4.6 s | C0 P48 78.3 s |
| l90-building | C0 P8238 192.3 s | C0 P8408 402.5 s |
| l90-hold | C0 P165 3.5 s | C0 P71 57.8 s |
| l90-room | C0 P537 13.8 s | C0 P59 112.5 s |

Joint's slowest run is 402.5 s on `l90-building` (180 s of stages plus greedy start plan 192 s, hint completion and build). The full-run estimate for large (about 20 hours) is likely low.

## Load 90, all methods
| Instance | greedy | joint | sequential | resolve | contract_net |
|---|---|---|---|---|---|
| building | C0 P8238 | C0 P8408 | C11 P14186 | C289 (all) | C104 P4887, 180.1 s |
| hold | C0 P165 | C0 P71 | C0 P95 | C0 P75 | C0 P165, 7.9 s |
| room | C0 P537 | C0 P59 | C1 P75 | C128 P64 | C0 P537, 29.0 s |

## Findings
1. **Resolve cancels most or all classes on large** (289 of 289 on `l90-building`, 128 on `l90-room`) while its status is `plan`. It has no start-plan hint; the cause (no good solution in its first stage) is not verified. A plan-rate count would hide this.
2. **Contract-net is limit-bound on `l90-building`**: greedy needs 192.3 s, longer than contract-net's 180 s cap, so its first auction was cut off and it ended with C104 against greedy's C0. It equals greedy on the other two and improves on neither.
3. Sequential cancels 11 and 1 classes on building and room; joint cancels none.

## Open decisions
- Contract-net cap on large (longer cap, or a cap that starts after the first auction); any change needs an ADR and all contract-net records from that code.
- Resolve on large: count a cancel-everything plan as a solver-limit failure in the report, and whether to give resolve a hint (changes the comparator; needs an ADR).
