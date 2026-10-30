# ADR-0004: R6 grouped encoding, greedy start plan, and why medium scenarios are not frozen yet

## Status
Accepted (the medium set is still open; see Consequences)

## Date
2026-10-30

## Context
The first frozen-set run (24 scenarios, small and medium, load 50 and 75) gave joint no plan within its 10 s first stage on 5 of the 12 medium scenarios: `medium-l50-building-s2`, `medium-l75-building-s1`, `medium-l75-hold-s2`, `medium-l75-room-s1`, `medium-l75-room-s2`. Greedy solved all 24. One of the failing runs (`medium-l75-room-s2`) took 297 s before giving up, far more than the solver budget.

Profiling `medium-l75-room-s2` split that time:

| Phase | Time |
|---|---|
| Building the model | about 285 s, of which R6 took about 279 s |
| Loading it into CP-SAT | about 1.4 s |
| Presolve | about 18 s |
| Search | none within 10 s |

Cause of the build time: `r6_people_conflict.post` looked at every pair of placement options (about 36,000 options, so hundreds of millions of pairs) in Python, and added one clause for each far-apart back-to-back pair. That left a model with 1.87 million constraints, and CP-SAT's presolve alone (about 20 s) used up the whole 10 s stage, so the search never started. With a 30 s limit and the greedy plan as a hint, stage 1 was solved (objective 0). The cancel-everything hint failed even then.

## Decision
- **R6 encoding.** For each person, options are grouped by (end time, building) and (start time, building). One literal per group says "some option of this group happens" (implied by each option; a fixed option makes it always true). For every time where a group of one building ends and a group of a far building (more than 10 minutes' walk) starts, one clause forbids both. The at-most-one-per-slot part is unchanged. The set of forbidden plans is the same as before; only the model is smaller. Medium build time dropped from about 285 s to 3 to 7 s, and the constraints from 1.87 million to 160k to 560k.
- **Check that the meaning did not change.** The existing validator/CP-SAT agreement tests pass unchanged. `tests/golden/test_r6_encoding.py` rebuilds the old pairwise encoding as a reference and, on all 12 small and 12 medium candidate scenarios, pins four plans (clean, back-to-back far, overlapping, back-to-back near) and requires the old encoding, the new one and the validator to give the same verdict. The reference only pairs the options the plans pick, because every other option is pinned to 0 and satisfies any pair clause; a full pairwise reference costs minutes per medium scenario.
- **Start plan.** `solve(..., hint=plan)` starts the search from a plan; the coordinator passes the greedy plan for `joint`. Without a hint the solver keeps the cancel-everything start.
- **Solver settings are not changed.** The spec split of 30 s as 10/10/3/3/2/2 stays as it is.
- **Frozen set.** `scenarios/frozen/` holds the 12 small scenarios. The 12 medium files stay in `scenarios/candidates/medium/` and are frozen in a later commit only if joint returns a plan on all 12.

## Result after the change (5 failing medium scenarios, 10 s first stage)
- Build 2.7 to 7.1 s; presolve 6.2 s to over 10 s; greedy 23 to 435 s.
- Joint now returns a plan on `medium-l50-building-s2` and still returns none on the other four. Presolve is over 5 s on all of them, so stage 1 gets little or no search time.

## Alternatives considered
- Raise the stage budget only: stage 1 would need about 30 s on medium, the whole run would pass the spec's 30 s, and the build would still take minutes.
- Turn presolve off or reduce probing: with presolve off the search started at 4.4 s but found no solution by 10 s; with probing off presolve still took over 10 s.
- Check and limit the pairs in Python (index options by start and end time) without changing the constraints: fixes the build time but keeps a model of the same size.

## Consequences
- Medium is not frozen. Open: presolve time (6 to 18 s) is larger than a 10 s stage. Next options are a smaller model elsewhere (R4, R5 and the objective expressions still add many constraints), or a new time split, which needs the user's decision.
- Greedy is slow on some medium scenarios (up to 435 s on `medium-l75-building-s1`), and `joint` now runs it first. Joint's wall time is greedy time plus 30 s.
- Changing the output of the generator for a seed still needs a new `GENERATOR_VERSION`; this change does not touch the generator.
