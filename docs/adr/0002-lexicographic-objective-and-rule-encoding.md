# ADR-0002: Lexicographic objective and single-source rule encoding

## Status
Accepted

## Date
2026-10-29

## Context
The recovery model must re-plan rooms, equipment and timing with minimal change, and the project claims "no plan from our system breaks a hard rule". Two things could undermine that: a weighted objective whose trade-offs are arbitrary and hard to defend, and a solver model and a validator that drift apart because each re-implements the rules.

## Decision
- The objective is lexicographic over six stages (cancellations, people moved, delay, cost, start shift, tie-break). Each stage's optimum is fixed as a constraint before the next stage runs.
- Each hard rule R1 to R8 lives in one module under `src/smartcampus/rules/` with a `check` (validator) and a `post` (CP-SAT encoding) built on the same predicates. A property test per rule asserts that the two agree on random small instances.

## Alternatives considered
- Weighted sum: needs weights that cannot be justified from data we do not have, and lets a large cost term hide a cancellation.
- Separate validator and solver constraints: simpler to write, but the two can silently disagree, which defeats the independent re-check in the recovery loop.

## Consequences
- Six solves per re-plan, with the 30 s budget split 10 / 10 / 3 / 3 / 2 / 2 s; a late stage can only refine, never worsen, an earlier one.
- Every rule is written twice in form (check and post) but once in meaning; the agreement tests carry the cost of keeping them aligned.
- Rule assumption literals make infeasible cores name the conflicting rules, which feeds the rejected-option explanations.
