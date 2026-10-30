# Prompt for the next session

Continue work on campus-ai (D:\Programming\campus-ai). CLAUDE.md and the memory-bank are loaded.

## State
- `main` is d179f78 (CI green: `checks` and `secrets`). The work since then is on local branch `feature/frozen-grid`. It was pushed to `origin/feature/generator` (the branch this environment designates) up to fe13523; the later commits (abfb433, dfc15db, 2177c64, bc5c265, c6e7ced, plus the docs commit) are local and NOT pushed. No PR is open; do not open one, push or merge without approval. Check `git log` and `git status` first.
- Frozen set: all 405 (small, medium, large x loads 50/75/90 x room/building/hold x seeds 1 to 15), 20 smoke instances are separate and not counted. Never edit files in `scenarios/frozen/`.
- Done this session: the 11 medium no-plans were a hint defect and are fixed (ADR 0006, `docs/results/medium-no-plan-diagnosis-2026-10-30.md`); large tier 60/60/18/18/12/12 s chosen from a pilot (`docs/results/large-tier-pilot-2026-10-30.csv`); baselines re-solve and sequential (spec section 9); eval harness, stats and report (`src/smartcampus/eval/`, spec section 10); `smartcampus eval` and `compare` work. 989 tests pass (about 8.5 min).
- NOT done: the full evaluation run. Joint has not been run on the 135 large frozen scenarios, and the small and medium plans were found before the hint fix, so everything is re-run once in the evaluation.

## Open items, in order
1. Ask the user when to run the full evaluation (405 instances x greedy, sequential, resolve, joint; expect many hours). Start it in the background: `uv run smartcampus eval scenarios/frozen/ --methods all --out results/ > var/eval.log 2>&1`, then Monitor `var/eval.log` (filter: `Traceback|Error|FAILED|Killed|run\(s\)`). It appends to `results/results.jsonl` and resumes if interrupted; do not run anything else timed at the same time. When done, copy `report.md` and a CSV into `docs/results/` (`results/` and `var/` are not for keeping) and write the reading: plan rate per method and per size, Wilcoxon on instances both solved, sensitivity view, remaining no-plans as a solver limit, threats to validity.
2. ITC 2019 loader: waits for the user's data files (`data/itc2019/`, gitignored). Ask the user.
3. Repair-overrun loop and approval triggers (spec section 6), then contract-net (add to `Method`, spec section 9, and the eval).
4. Optional: greedy still rebuilds `fixed_placements` and `placements` for every rule on every `validate` call (about 10% of its time); R1/R2 `check` speed on large; hint completion takes a few seconds before stage 1 on medium and large (not in the stage budget).

## Environment (Windows)
- `export PATH="$HOME/.local/bin:$PATH"` for uv. gh is at "C:\Program Files\GitHub CLI\gh.exe" (sohanroy676).
- Write files as UTF-8 without BOM. Docs and memory-bank files use CRLF in the working copy; in Python pass `encoding="utf-8"` and `newline=""`. Use the Write and Edit tools for long files; shell heredocs with backslashes mangle escapes (a `"\n"` became a real newline in `cli.py`).
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. After a push, watch CI with Monitor (`gh run watch` / `gh pr checks`), report every terminal state including `secrets`, and do not report green unless seen.
- A Monitor expires after 30 minutes at most; for long runs write to a log and watch the log. A background `nohup ... &` launcher reports "completed" at once; that is not the job finishing, so watch the log. Do not run two timed jobs at once (they share the CPU).
- `var/` is gitignored. `time.monotonic()` has about 15 ms resolution on Windows, so very short timings read 0.
- Chain commands with care: `a && b; git commit` still commits when `a` fails. Run lint before staging.

## Known facts that matter
- `SolverSettings.for_problem(problem)` picks the tier from `provenance.size`: small 10/10/3/3/2/2 s, medium 30/30/9/9/6/6 s, large 60/60/18/18/12/12 s; no provenance counts as small. `SolverSettings.skip_stages` leaves stages out (re-solve and the sequential passes use it).
- `solve(problem, settings, hint=, restrict=)`: `hint` is completed by `_complete_hint` before stage 1; `restrict(ctx)` may fix or forbid decision variables only, never encode a rule.
- `RunResult.planning_seconds` and `start_plan_seconds` (joint's greedy part) feed the eval's separate greedy and joint times.
- The golden tests for the old R6, R4 and R5 encodings use only the original 24 scenarios (glob `*-l[57][05]-*-s[12].json`); the old encodings are too slow for all of them. `test_frozen_set.py` regenerates all 405 files byte for byte.
- `DecisionVars` has shared literals (`any_happens`, `building_start_literals`, `start_literals`, `placed_literal`, `start_bounds`). `stage_expression(ctx, i)` builds one stage; `stage_expressions(ctx)` returns all six.
- `large-l90-room-s102` (pilot seed, not frozen) ends with 1 cancellation on both tiers with every stage at its time limit; that cancellation is not proven necessary.
- Scratch scripts for the timing runs were in the session scratchpad (not in the repo); `smartcampus eval --pattern` now does the same job on a subset (for example `--pattern "small-l75-*-s[12].json"`).
