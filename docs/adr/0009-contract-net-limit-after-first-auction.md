# ADR-0009: Contract-net's time limit starts after its first auction

## Status
Accepted

## Date
2026-10-31

## Context
Contract-net's initial auction equals greedy (same order, same costs) and is as slow as greedy: 192 s on `large-l90-building-s2`. The wall-clock limit was the tier's total solver seconds (180 s on large) and covered the whole run, so the limit ended the first auction early. The run ended with 104 cancellations against greedy's 0 (`docs/results/large-check-2026-10-31.md`). Joint does not have this problem: its greedy start plan is built first and the tier's seconds are for the search after it.

## Decision
The initial auction has no time limit. The limit (small 30 s, medium 90 s, large 180 s, the tier's total solver seconds) starts when the initial auction ends and bounds the re-auction rounds. This is the same structure as joint (greedy start plan, then the tier's seconds). The result is never worse than greedy's. Each record shows the initial auction's time as `start_plan_seconds` and whether the rounds were cut off as `limit_hit`. Spec section 9 (contract-net step 3) and the threats are updated. All contract-net records come from code at or after this change.

## Alternatives considered
- A longer fixed cap on large (for example 400 s). Rejected: it is arbitrary, still breaks if a first auction takes longer, and differs from joint's structure.
- A cap of greedy's time plus the tier's seconds measured per run. Same effect as the decision, but the limit would depend on the machine twice; starting the clock after the first auction is simpler.
- Leave it and report the large result as limit-bound. Rejected: it would measure the first auction's speed, not the negotiation.

## Consequences
- Contract-net's wall time on large is up to the first auction (about 190 s) plus 180 s, like joint's.
- Nothing is lost on small and medium, where the first auction was well inside the limit.
- Contract-net can no longer be worse than greedy; if it equals greedy, `start_unimproved` says so.
- The rounds completed on large still depend on CPU speed (stated in the threats).
