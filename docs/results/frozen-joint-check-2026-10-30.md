# Joint on the newly frozen scenarios (2026-10-30)

Scope: 240 of the 246 newly frozen scenarios (the 6 medium load 90 seed 1 and 2 scenarios were timed earlier, see `solver-timing-2026-10-30.md`). Greedy and joint run one after the other, one job at a time, `num_workers=1`, seed 42, medium tier 30/30/9/9/6/6 s (90 s), small tier 10/10/3/3/2/2 s (30 s). Joint gets the greedy plan as a hint. Rows: `frozen-joint-check-2026-10-30.csv`. Greedy and joint times are separate columns (`greedy_s`, `joint_s`).

## Result

| size | load | scenarios | plan | no plan |
|---|---|---|---|---|
| small | 50 | 39 | 39 | 0 |
| small | 75 | 39 | 39 | 0 |
| small | 90 | 45 | 45 | 0 |
| medium | 50 | 39 | 39 | 0 |
| medium | 75 | 39 | 34 | 5 |
| medium | 90 | 39 | 33 | 6 |

Joint returned a plan on 229 of 240 and no plan on 11, all medium, none small. By severity: 5 hold, 5 room, 1 building.

No plan:
`medium-l75-building-s15`, `medium-l75-hold-s15`, `medium-l75-hold-s6`, `medium-l75-room-s13`, `medium-l75-room-s7`, `medium-l90-hold-s10`, `medium-l90-hold-s5`, `medium-l90-hold-s9`, `medium-l90-room-s10`, `medium-l90-room-s3`, `medium-l90-room-s8`.

## Times (seconds)

| size | greedy median / max | joint median / max (plans only) |
|---|---|---|
| small | 0.9 / 23.3 | 2.1 / 31.6 |
| medium | 2.8 / 184.7 | 23.0 / 95.9 |

Greedy times for medium load 90 building are the longest (up to 184.7 s).

## Observations

- Every no-plan run ended after 32.4 to 33.9 s, far short of the 90 s medium budget. That is about the first stage limit (30 s) plus model build, so the cause is probably that the first stage found no solution within its limit. This is a guess from the timings; it was not checked (no solver log was kept).
- No per-load tier is added. These are reported as a solver limit.

## Open

The frozen set has 270 scenarios, so the user must decide how to fill the count of the 405 given these 11 (and whether to look at the first-stage failure before deciding).
