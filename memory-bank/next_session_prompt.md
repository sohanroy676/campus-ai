# Prompt for the next session

Continue work on campus-ai (D:\Programming\campus-ai). CLAUDE.md and the memory-bank are loaded. Read this file first, then check `git log` and `git status`.

## State
- `main` is d179f78 (CI green). All work since then is on `feature/frozen-grid`, pushed to `origin/feature/generator` (the branch this environment designates). No PR is open; do not open a PR or merge without approval.
- Frozen set: all 405 instances in `scenarios/frozen/` (small, medium, large x loads 50/75/90 x room/building/hold x seeds 1 to 15); 20 smoke instances are separate and not counted. Never edit files in `scenarios/frozen/`.
- Built: rules R1 to R8, CP-SAT solver with six lexicographic stages and a complete start-plan hint, event log, impact derivation, generator, four methods (greedy, sequential, resolve, joint), eval harness/stats/report, CLI `run`, `generate`, `compare`, `eval`. Time tiers: small 10/10/3/3/2/2 s, medium 30/30/9/9/6/6 s, large 60/60/18/18/12/12 s. 989 tests pass (about 8.5 min).
- Decision (ADR 0007): implement every remaining feature first and run the full 405-instance evaluation once at the end. It is estimated at 24 to 36 hours (about 20 of them on large). Do not start it until the user says the code is frozen.

## Open items, in order
1. Repair-overrun loop and approval triggers (spec section 6; the demo cascade is "AC failure, then a repair overrun" and is a success criterion). `sim/` already has the events and stale-plan rejection, and `impact/derive_recovery` re-derives the window and movable set from the state. `run` currently applies the plan directly. Plan it, show the user the plan, then build on a feature branch.
2. Contract-net. Write a short spec definition (add it to spec section 9) and show it to the user BEFORE coding, as was done for sequential. Add it to `Method`, the CLI and the eval. No rule logic in agents; state changes only by appending events; the LLM never checks rules or picks plans.
3. Stamp each eval record with the git commit, the solver settings and the generator version (`eval/metrics.py` `RunRecord`, `eval/harness.py`), so a kept result can be traced to its code.
4. Cheap checks, not reported as results: one seed per grid cell (27 instances, about 2 hours) to look for large no-plans; a subset of about 20 instances after each new method. Run with `uv run smartcampus eval scenarios/frozen/ --pattern "<glob>" --out var/<name>/ > var/<name>.log 2>&1` in the background and Monitor the log (filter: `Traceback|Error|FAILED|Killed|run\(s\)`). One timed job at a time. If large no-plans remain, pilot a different large tier before the full run.
5. Optional: results view (FastAPI and a simple React page); ITC 2019 loader (ask the user whether the data files exist in `data/itc2019/`, gitignored; skip if not).
6. When the user says the code is frozen: the full run `uv run smartcampus eval scenarios/frozen/ --methods all --out results/ > var/eval.log 2>&1`, resumable from `results/results.jsonl`. Then copy `report.md` and a CSV into `docs/results/` and write the reading: plan rate per method and per size, Wilcoxon on instances both solved, sensitivity view, remaining no-plans as a solver limit, threats to validity.
7. Low priority: greedy rebuilds `fixed_placements` and `placements` for every rule on every `validate` call (about 10% of its time); R1/R2 `check` speed on large; hint completion takes a few seconds before stage 1 (outside the stage budget); `large-l90-room-s102` (pilot seed, not frozen) ended with 1 cancellation on both tiers with every stage at its time limit, not proven necessary.
8. The user still needs to schedule the officer and facilities interviews (ROADMAP "Now"); the officer review of 5 plans depends on them.

## Environment (Windows)
- `export PATH="$HOME/.local/bin:$PATH"` for uv. gh is at "C:\Program Files\GitHub CLI\gh.exe" (sohanroy676).
- Write files as UTF-8 without BOM. Docs and memory-bank files use CRLF in the working copy; in Python pass `encoding="utf-8"` and `newline=""`. Use the Write and Edit tools for long files; shell heredocs with backslashes mangle escapes.
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Run ruff check, ruff format, mypy src and the full pytest (in the background, Monitor the log) before each commit. After a push, watch CI with Monitor (`gh run watch` / `gh pr checks`), report every terminal state including `secrets`, and do not report green unless seen.
- A Monitor expires after 30 minutes at most; for long runs write to a log and watch the log. A background `nohup ... &` launcher reports "completed" at once; that is not the job finishing. Do not run two timed jobs at once (they share the CPU). `var/` is gitignored. `time.monotonic()` has about 15 ms resolution on Windows.

## Known facts that matter
- `SolverSettings.for_problem(problem)` picks the tier from `provenance.size` (no provenance counts as small). `SolverSettings.skip_stages` leaves stages out (resolve and the sequential passes use it).
- `solve(problem, settings, hint=, restrict=)`: `hint` is completed by `_complete_hint` before stage 1; `restrict(ctx)` may fix or forbid decision variables only, never encode a rule.
- `RunResult.planning_seconds` and `start_plan_seconds` (joint's greedy part) feed the eval's separate greedy and joint times.
- The golden tests for the old R6, R4 and R5 encodings use only the original 24 scenarios (glob `*-l[57][05]-*-s[12].json`). `test_frozen_set.py` regenerates all 405 files byte for byte.
- `DecisionVars` has shared literals (`any_happens`, `building_start_literals`, `start_literals`, `placed_literal`, `start_bounds`). `stage_expression(ctx, i)` builds one stage.
- Results records: `results.jsonl` in the `--out` directory, one JSON line per (instance, method); a method with no plan is a `no_plan` record scored as cancel-everything in the sensitivity view.
