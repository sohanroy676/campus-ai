# Prompt for the next session

Continue work on campus-ai (D:\Programming\campus-ai). CLAUDE.md and the memory-bank are loaded. Read this file first, then check `git log` and `git status`. Do not push or open a PR without my approval. Do not start the full 405-instance evaluation until I say the code is frozen.

## State (2026-10-31)
- `feature/freeze-prep` was merged into `main` and pushed with the user's approval (verify with `git log`; check CI on `main` finished green with `checks` and `secrets`, using Monitor). Older feature branches still exist; do not delete any branch.
- All five methods exist (greedy, sequential, resolve, joint, contract_net), plus the harness, stats, report, the recovery loop (`cascade`) and approval triggers. 1115 tests pass (about 13 min); ruff and mypy are clean.
- The pre-freeze decisions are implemented (details in `progress.md`): ADR 0009 (contract-net's limit starts after its first auction), ADR 0010 (resolve gets the greedy start-plan hint), records with `limit_hit` and `start_unimproved`, `manifest.json` (refuses a resume under another commit or environment), wall time beside stage seconds, primary and secondary comparisons with Holm (spec 10), greedy speed-up (cached fixed placements; plans identical on 29 golden instances), `scenarios/smoke/` (20 instances, seeds 201 to 220), ADR 0007 update (time estimate about 20 h, up to 30 h; run-safety list; mid-run bug policy).
- Large re-check (`docs/results/large-recheck-2026-10-31.md`): contract-net C0 and resolve C0 on the three load-90 large instances.
- The code is READY TO FREEZE but the user has not said so. Not done on purpose: tag, dry run, full run.

## Next steps, in order
1. Wait for the user to say the code is frozen. Then tag the commit (for example `v1.0-eval`), run the dry run on `scenarios/smoke/` with all five methods, `report.md` included, at the tagged commit; check it by eye; kill it once and confirm it resumes; delete those results.
2. Start the full run only on the user's word: clean tree, empty `results/`, sleep disabled, memory log and Monitor, one timed job at a time (ADR 0007): `uv run smartcampus eval scenarios/frozen/ --methods all --out results/ > var/eval.log 2>&1` in the background, Monitor `var/eval.log` (cover failure strings). Re-estimate the time after the first 40 large records. Bug policy: a fix to shared code restarts the run; a fix inside one method deletes and re-runs only that method (ADR 0007).
3. Then copy `report.md` and a CSV into `docs/results/` and write the reading: plan rate per method and size, the primary comparison (joint vs sequential, C and P, Holm), the secondary family, sensitivity view, `limit_hit` and `start_unimproved` counts, remaining no-plans as a solver limit, threats to validity.
4. The user still needs to schedule the officer and facilities interviews (ROADMAP "Now"); the officer review of 5 plans depends on them.
5. Optional, only if asked: results page (FastAPI and React), ITC 2019 loader (needs data files in `data/itc2019/`, gitignored), `approve`/`reject` command for a pending plan, a demo script.

## Environment (Windows)
- `export PATH="$HOME/.local/bin:$PATH"` for uv. gh is at "C:\Program Files\GitHub CLI\gh.exe" (sohanroy676).
- Write files as UTF-8 without BOM. Docs and memory-bank files use CRLF in the working copy; in Python pass `encoding="utf-8"` and `newline=""`. Use the Write and Edit tools for long files; shell heredocs with backslashes or triple quotes mangle text (write a script file with the Write tool, then run it).
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Before each commit run ruff check, ruff format, mypy src and the full pytest in the background and Monitor the log. A `&&` chain with `| tail` hides a ruff failure: check the output. After a push to `main` or a PR, watch CI with Monitor (`gh run watch` / `gh pr checks`) and do not report green unless seen.
- Monitors expire after 30 minutes; for long runs watch the results file and the process. A Monitor started right after a background launch can see no process yet: wait first. Sleep in the foreground is blocked. Do not run two timed jobs at once (shared CPU). `var/` is gitignored. `time.monotonic()` has about 15 ms resolution on Windows.

## Known facts that matter
- `SolverSettings.for_problem(problem)` picks the tier from `provenance.size`: small 10/10/3/3/2/2 s, medium 30/30/9/9/6/6 s, large 60/60/18/18/12/12 s. `skip_stages` leaves stages out (resolve and the sequential passes).
- `solve(problem, settings, hint=, restrict=)`: `hint` is completed by `_complete_hint` before stage 1; `restrict` may fix or forbid decision variables only, never encode a rule.
- `coordinator/run.plan_with_method` builds and re-checks a plan for any method; `run_scenario` seeds the disruptions, calls it and applies the plan; `coordinator/loop.recover` is the cascade version.
- Contract-net: `run_contract_net` returns `AuctionResult` (plan, start plan, start-plan seconds, `limit_hit`); the initial auction equals greedy and has no limit; up to 5 re-auction rounds under the tier's total seconds.
- Eval harness: greedy runs first per instance (its values are the start solution for `start_unimproved`); `check_or_write` ties a results directory to one commit and environment.
- Goldens: `test_frozen_set.py` (all 405 byte for byte), `test_smoke_set.py` (20), `test_greedy_unchanged.py` (29 greedy plans; the large half is marked `slow`). The old R6/R4/R5 encoding goldens use only the original 24 scenarios. Never edit `scenarios/frozen/`.
- Results records: `results.jsonl` in the `--out` directory, one JSON line per (instance, method); a method with no plan is a `no_plan` record scored as cancel-everything in the sensitivity view.
