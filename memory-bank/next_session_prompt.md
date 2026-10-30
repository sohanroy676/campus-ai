# Prompt for the next session

Continue work on campus-ai (D:\Programming\campus-ai). CLAUDE.md and the memory-bank are loaded.

## State
- `main` holds everything through `feature/medium-tier`: the medium time tier (ADR 0005), 24 frozen scenarios (12 small, 12 medium), the faster greedy (R6 `check` indexed by person), spec assumptions 1-24 confirmed (2026-10-30) and the scenario count settled. Check `git log` and the CI runs, and confirm `checks` and `secrets` were green. 543 tests.
- Scenario count: the frozen v1.0 evaluation set is 405 instances; 20 smoke instances are separate and not counted. 24 of 405 are frozen. Do not state any other target; Gate 2 reports progress against 405.
- Joint solves all 12 medium scenarios with the 30/30/9/9/6/6 s tier (small keeps 10/10/3/3/2/2 s). Large has no measured tier yet and reuses the medium one.
- Merged feature branches still exist; do not delete them. Never edit `scenarios/frozen/`.

## Open items, in order
1. Grow the frozen set toward 405: decide the grid (sizes, loads, severities, seeds; large needs a measured time tier) and write it into the spec and `tests/golden/test_frozen_set.py`. Bump `GENERATOR_VERSION` only if output for a seed changes.
2. Sequential and re-solve baselines (`baselines/`), then the eval harness and stats (Gate 2): medians and IQR, win/tie/loss, paired Wilcoxon, `num_workers=1`, seed 42.
3. ITC 2019 loader: waits for the user's data files (`data/itc2019/`, gitignored). Ask the user.
4. Repair-overrun loop and approval triggers (spec section 6), then contract-net.
5. Optional: greedy is still about 112 s on `medium-l75-building-s1`; the rest is the R2 and R1 `check` (index them like R6, same output order).

## Environment (Windows)
- `export PATH="$HOME/.local/bin:$PATH"` for uv. gh is at "C:\Program Files\GitHub CLI\gh.exe" (sohanroy676).
- Write files as UTF-8 without BOM; in Python pass `encoding="utf-8"` and `newline=""` (docs and memory-bank files use CRLF in the working copy). Use the Write tool for long files.
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do not push or merge without approval. After a push, watch CI with Monitor (`gh run watch` / `gh pr checks`), report every terminal state including `secrets`, and do not report green unless seen.
- A Monitor expires after 30 minutes at most; for long runs write to a log and watch the log. Do not run two timed jobs at once (they share the CPU and can fail a time-limited solve).
- The full suite takes about 7 minutes (run it in the background and watch it with Monitor).

## Known facts that matter
- `SolverSettings.for_problem(problem)` picks the tier from `provenance.size`; no provenance counts as small.
- `DecisionVars` has shared literals (`any_happens`, `building_start_literals`, `start_literals`, `placed_literal`, `start_bounds`). They are "implied by" literals except `placed_literal`.
- `stage_expression(ctx, i)` builds one stage; `stage_expressions(ctx)` returns all six (tests use it).
- In a loop log that prints the score before the next header, a score belongs to the scenario above its header line.
