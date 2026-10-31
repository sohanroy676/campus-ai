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
- The records carry the git commit ("+dirty" if the tree had uncommitted changes), the generator version, and the solver tier, workers and seed (done 2026-10-30). The report names the code and warns when one results file mixes commits or holds unstamped runs; start the final run from a clean tree and an empty `results/`.

## Update 2026-10-31: pre-freeze decisions

### Changes made before the freeze
ADR 0009 (contract-net's limit starts after its first auction), ADR 0010 (re-solve gets the greedy start-plan hint), records with `limit_hit` and `start_unimproved` and a run manifest, wall time beside stage seconds in the report, a primary and secondary comparison with Holm correction (spec section 10), and a faster greedy (fixed placements cached in `rules/_shared.py`; plans are byte for byte the same on 29 golden instances, `tests/golden/test_greedy_unchanged.py`; greedy on `large-l90-building-s2` 192 s to 105 s). The 20 smoke instances are in `scenarios/smoke/` (seeds 201 to 220, 10 small, 8 medium, 2 large).

### Time estimate for the full run (405 instances x 5 methods, one job at a time)
Measured mean seconds per instance and method. Small and medium: 3 smoke instances each (`var/est-out`, not committed), new code. Large: the 9 large-check instances for greedy and joint (joint's greedy start plan was slower then, so it is an upper value), and the 3 load-90 instances for the other methods (the re-check of 2026-10-31 for greedy, contract-net and resolve; the first large check for sequential). Load 90 is the heaviest load, so the large means below are high for the whole grid.

| size | greedy | joint | resolve | sequential | contract-net | per instance | x 135 |
|---|---|---|---|---|---|---|---|
| small | 1.7 | 10.1 | 6.0 | 4.0 | 7.2 | 29 s | 1.1 h |
| medium | 6.4 | 15.1 | 14.2 | 9.7 | 38.0 | 83 s | 3.1 h |
| large, point estimate | 25 | 145 | 100 | 90 | 70 | 430 s | 16.1 h |
| large, all like load 90 | 38 | 191 | 133 | 119 | 96 | 577 s | 21.6 h |

Total: about 20 h as the point estimate, 26 to 30 h if large is everywhere as slow as load 90. The expectation "more than 36 h" is not supported by these numbers; small and medium finish well inside their tiers because stages end at the optimum. Plan for up to 36 h to leave room for a pause or a restart, and treat 36 h as the planning bound, not as the estimate. Uncertainties: three instances per small and medium cell, large sequential/resolve/contract-net measured on load 90 only, and the machine's speed varies with other load. The first 40 large records will give a better figure; re-estimate then.

### Run safety (before the start)
1. Clean tree, tagged commit, and an empty `results/` (the harness refuses a directory whose `manifest.json` names another commit or environment, or one with records but no manifest).
2. The CPU model, OS, Python, OR-Tools, NumPy and SciPy versions are in `results/manifest.json`; the commit is in every record.
3. Disable sleep and hibernate for the run: `powercfg /change standby-timeout-ac 0`, `powercfg /change hibernate-timeout-ac 0`, `powercfg /change monitor-timeout-ac 0`; plug in the machine and stop Windows Update restarts. Restore afterwards.
4. Resume after a kill: `tests/unit/test_eval_manifest.py` kills `run_eval` between records and checks that a re-run adds no duplicates; before the full run, kill the dry run once (`taskkill` on the python process) and restart it from the same `--out`.
5. Memory: the first large check was killed once by the system for low memory. Log the working set of the python process every minute (`while true; do tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH >> var/mem.log; sleep 60; done`) and put a Monitor on the log that reports when it passes a threshold (for example 12 GB) or when the process disappears; the run resumes from `results.jsonl`.
6. One timed job at a time; nothing else runs on the machine (no test suite, no second eval).

### Mid-run bug policy
- A fix to shared code (rules, solver, model, generator, harness scoring, the report's scoring of records) means restarting the whole run: delete `results/` and start again from the new tagged commit.
- A fix inside one method's own code (its module in `baselines/` or `agents/` and nothing it shares) means deleting only that method's records from `results.jsonl` and re-running them. The commit changes, so the manifest and the records must carry it: write the new commit as a new manifest and keep the old one as `manifest-<commit>.json`; the report warns on mixed commits and the reading must say which methods come from which commit.
- Never mix commits silently in one results file: the harness refuses a resume under another commit, so a deliberate partial re-run needs the manifest step above and a note in the reading.
- A cosmetic fix to the report or CLI output (not the records) needs no re-run.

### Dry run
After the freeze (tag), run the whole pipeline on `scenarios/smoke/` at the tagged commit with all five methods and `report.md`, check it by eye, delete those results, then start the 405 run.

