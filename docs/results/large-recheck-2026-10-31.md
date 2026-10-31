# Large re-check after ADR 0009 and 0010, 2026-10-31

Not a result of the evaluation: a check that the two defects found in `large-check-2026-10-31.md` are fixed. Code at 0501b34 plus the uncommitted pre-freeze changes (records marked "+dirty"), `num_workers=1`, `random_seed=42`, large tier 60/60/18/18/12/12 s, one job at a time. Instances: `large-l90-{building,hold,room}-s2`. Methods: greedy (with the cached fixed placements, plans identical), contract-net (limit after the first auction, ADR 0009) and resolve (greedy start-plan hint, ADR 0010). Joint and sequential were not re-run (their code is unchanged).

| Instance | Method | C | P | wall s | start plan s | limit hit | start unimproved |
|---|---|---|---|---|---|---|---|
| building | greedy | 0 | 8238 | 104.7 | - | no | yes (by definition) |
| building | contract_net | 0 | 8238 | 265.7 | 108.6 | no | yes |
| building | resolve | 0 | 8408 | 297.2 | 104.8 | yes | yes |
| hold | greedy | 0 | 165 | 2.4 | - | no | yes |
| hold | contract_net | 0 | 165 | 5.1 | 2.4 | no | yes |
| hold | resolve | 0 | 75 | 36.7 | 2.4 | no | no |
| room | greedy | 0 | 537 | 7.6 | - | no | yes |
| room | contract_net | 0 | 537 | 17.3 | 7.9 | no | yes |
| room | resolve | 0 | 525 | 64.5 | 7.7 | yes | no |

## Findings
1. **Contract-net**: on `building` it now ends at greedy's plan (C0, was C104 with its 180 s cap spent inside the first auction). It improves on greedy on none of the three: the re-auction rounds found no strictly better whole plan, so on load 90 large it equals greedy. The earlier subset check (14 instances) found gains on 9, mostly small and medium.
2. **Resolve**: with the hint, no cancel-everything or heavy-cancel plan (was C289 and C128). C is 0 on all three. On `building` it ends at P 8408, above greedy's 8238 (it does not minimise P, and it hit its time limit); on `hold` and `room` P is below greedy's. Its flag `start_unimproved` is yes on `building`: there the search found nothing better than the start on the lexicographic order.
3. **Greedy time** on `l90-building-s2`: 192.3 s before, 104.7 s with the cached fixed placements (`rules/_shared.py`); the plans are byte for byte the same on the 29 golden instances (`tests/golden/test_greedy_unchanged.py`). R1 and R2 `check` were already indexed (the profile shows the cost in rebuilding fixed placements 70546 times and in R4, R6, R8 `check`, not in R1/R2).

Raw records: `var/large-check-c/results.jsonl` (gitignored).
