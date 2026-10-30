# ADR-0007: Implement every feature first, run the full evaluation once at the end

## Status
Accepted

## Date
2026-10-30

## Context
The evaluation harness exists (`smartcampus eval`), and four of the five comparators are built (greedy, sequential, re-solve, joint). The full run is 405 instances x every method. The estimate is 24 to 36 hours of wall time (about 20 hours of it on large), one timed job at a time; this is an estimate from earlier timings, and resolve and sequential on large have not been measured. Results depend on CPU speed because stages stop at time limits, so runs should not overlap. A change to the solver, the rules, the time tiers or the generator makes earlier records stale. Contract-net, the repair-overrun loop and the approval triggers are not built yet, and either could change `solve()` or `run_scenario`. Eval records do not yet store the code version.

## Decision
Build the remaining features first (repair-overrun loop and approval triggers, then contract-net), freeze the code, and run the full 405-instance evaluation once for all five methods. Until then, run only small checks:
- one seed per grid cell (27 instances, about 2 hours) before contract-net, to find large no-plans early, because that is the one result that could force a new large tier;
- a subset of about 20 instances after each new method, to check the harness and read the report by eye.

Neither check is reported as a result. Before any run that is kept, each record stores the git commit, the solver settings and the generator version.

## Alternatives considered
- Run the full evaluation now and add contract-net later. The results file resumes, so the four finished methods would not repeat, but any later code change would make those records stale, and the run could cost a day twice or more. Rejected.
- Run nothing until the end. Rejected: a bug in the harness or stats, or large no-plans, would show up only after a day of compute.

## Consequences
- One expensive run, with every comparator on the same code, so the results can be traced to one commit.
- Large no-plans and harness defects are found early by the cheap checks, not at the end.
- The evidence for the headline question (does joint beat sequential, can contract-net match it) arrives late; if time runs short, the optional results page is cut before the evaluation is.
- The records need the code version added before the final run (to do).
