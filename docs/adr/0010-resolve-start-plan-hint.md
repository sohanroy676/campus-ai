# ADR-0010: Re-solve gets the greedy start-plan hint

## Status
Accepted

## Date
2026-10-31

## Context
Re-solve (P, D, S stages dropped, no hint) returned status `plan` with a cancel-everything or heavy-cancel plan on large instances: 289 of 289 classes cancelled on `large-l90-building-s2`, 128 on `large-l90-room-s2` (`docs/results/large-check-2026-10-31.md`), while greedy cancels 0 there. Joint, with the complete greedy hint (ADR 0006), cancels 0. Without a hint the first stage found only a poor first solution within its time. That result measures the missing hint, not the re-solve idea.

## Decision
Re-solve gets the same complete greedy start-plan hint as joint, through the same `_complete_hint` path (ADR 0006). It stays the "re-solve from scratch" comparator because its objective is what defines it: stages P, D and S are dropped, C, K and T are kept, and the hint only guides search. Its planning time includes the greedy start plan, as for joint (`start_plan_seconds`). The threats to validity say so. Spec section 9 is updated. All re-solve records come from code at or after this change.

## Alternatives considered
- Keep it hint-free and report cancel-everything plans as solver-limit failures. Rejected: it would make the strongest "joint beats re-solve" result come from a search failure.
- A different comparator that ignores the timetable (no start plan at all, from scratch). Rejected: that is what the hint-free run was, and it fails for search reasons.

## Consequences
- Re-solve's C stage can no longer end worse than greedy's C (the hint is a feasible solution), so a heavy-cancel plan on large would now be a real finding.
- Re-solve and joint share the start plan, so differences between them come from the objective (P, D, S stages) and not from the start.
- A re-solve that ends no better than the start plan is counted in `start_unimproved`.
- Time per large instance rises by the greedy start plan (up to about 190 s).
