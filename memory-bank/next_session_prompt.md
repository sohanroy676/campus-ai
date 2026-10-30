# Prompt for the next session

Continue work on campus-ai (D:\Programming\campus-ai). CLAUDE.md and the memory-bank are loaded.

## State
- `main` is d179f78 (CI green: `checks` and `secrets`). The work since then is on local branch `feature/frozen-grid`, pushed to `origin/feature/generator` (the branch this environment designates). No PR is open; do not open one or merge without approval. Check `git log` and `git status` first.
- Frozen set: 270 of 405 (135 small, 135 medium: loads 50/75/90 x room/building/hold x seeds 1 to 15). 135 large are not frozen. 20 smoke instances are separate and not counted. Do not state any other target.
- R1 and R2 `check` are indexed; greedy on the slowest medium went 321 s to 89.5 s. 801 tests pass (about 7 min).
- All timing runs so far are in `docs/results/solver-timing-2026-10-30.md` and `.csv` (medium load 90: 6 of 6 plans; large with the medium tier: 7 of 9 plans, no plan on `large-l75-building-s1` and `large-l90-room-s1`, presolve about 15 s).
- Merged feature branches still exist; do not delete them. Never edit `scenarios/frozen/`.

## Open items, in order
1. Run joint on the 246 frozen scenarios not yet checked (small load 90; seeds 3 to 15 for every size/load/severity; medium load 90 seeds 3 to 15). One timed job at a time, `num_workers=1`, seed 42, in the background with a log and Monitor. Report plan/no-plan, greedy time and joint time separately, and write the summary into `docs/results/`. If any have no plan, do not add a per-load tier: report them as a solver limit and ask the user how to fill the count.
2. Large time tier (needs the user's go-ahead): test 60/60/18/18/12/12 s on `large-l75-building-s1` and `large-l90-room-s1`, then seeds 2 and 3. If presolve is the cause, consider a model fix before a longer tier. Then write the tier into `SolverSettings.for_problem`, spec section 5 and an ADR, and freeze large seeds 1 to 15 (update `test_frozen_set.py`).
3. Baselines in `baselines/`: sequential per-domain repair (rooms, then equipment, then timing; needs a short spec definition first) and re-solve from scratch. Re-solve is decided: a full joint solve ignoring the existing timetable, stages P, D, S dropped, C, K and T kept, no start-plan hint, same total budget as the scenario's tier with the freed time given to C and K; P, D, S are still computed on its plan. Add both to `Method` in `coordinator/run.py`.
4. Eval harness and stats (Gate 2): `eval/metrics.py`, `harness.py`, `stats.py`; medians and IQR, win/tie/loss, paired Wilcoxon (scipy is a dependency), `num_workers=1`, seed 42; report greedy and joint time separately; wire `eval` and `compare` in the CLI.
5. ITC 2019 loader: waits for the user's data files (`data/itc2019/`, gitignored). Ask the user.
6. Repair-overrun loop and approval triggers (spec section 6), then contract-net.
7. Optional: greedy still rebuilds `fixed_placements` and `placements` for every rule on every `validate` call (about 10% of its time).

## Environment (Windows)
- `export PATH="$HOME/.local/bin:$PATH"` for uv. gh is at "C:\Program Files\GitHub CLI\gh.exe" (sohanroy676).
- Write files as UTF-8 without BOM; in Python pass `encoding="utf-8"` and `newline=""` (docs and memory-bank files use CRLF in the working copy). Use the Write tool for long files.
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do not push or merge without approval. After a push, watch CI with Monitor (`gh run watch` / `gh pr checks`), report every terminal state including `secrets`, and do not report green unless seen.
- A Monitor expires after 30 minutes at most; for long runs write to a log and watch the log. A background `nohup ... &` launcher reports "completed" at once; that is not the job finishing, so watch the log. Do not run two timed jobs at once (they share the CPU).
- `var/` is gitignored: put summaries in `docs/results/`, not only in logs.
- Chain commands with care: `a && b; git commit` still commits when `a` fails. Run lint before staging.

## Known facts that matter
- `SolverSettings.for_problem(problem)` picks the tier from `provenance.size`; no provenance counts as small; large reuses the medium tier (30/30/9/9/6/6 s) until a large tier is measured.
- The golden tests for the old R6, R4 and R5 encodings use only the original 24 scenarios (glob `*-l[57][05]-*-s[12].json`); the old encodings are too slow for all 270.
- `DecisionVars` has shared literals (`any_happens`, `building_start_literals`, `start_literals`, `placed_literal`, `start_bounds`). They are "implied by" literals except `placed_literal`.
- `stage_expression(ctx, i)` builds one stage; `stage_expressions(ctx)` returns all six (tests use it).
- `room_closures(problem)` in `rules/_shared.py` lists per-room closed intervals for the R2 check; `is_closed` (used by `post`) still uses the scanning predicates.
- Scratch scripts for the timing runs were in the session scratchpad (not in the repo): run `run_scenario` for JOINT with a patched `CpSolver` that logs "Starting search at" for presolve time; time `greedy` separately.
