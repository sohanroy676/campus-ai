# Prompt for the next session

Continue work on campus-ai (D:\Programming\campus-ai). CLAUDE.md and the memory-bank are loaded.

## State
- `main` holds the generator (PR #6) and, after this session's PR, the frozen small set, the smaller R4/R5/R6/objective models and the greedy start plan. Check `git log` and `gh pr list` to confirm what landed and that CI was green (`checks` and `secrets`). 515 tests.
- `scenarios/frozen/` holds 12 small scenarios (never edit them). The 12 medium scenarios are candidates in `scenarios/candidates/medium/`, not frozen.
- ADR-0004 has the numbers. Merged feature branches still exist; do not delete them.

## Open decision (ask the user first)
Joint returns a plan on 10 of 12 medium scenarios; still none on `medium-l75-hold-s2` (presolve 5.0 s) and `medium-l75-room-s2` (presolve 4.3 s, no solution in the 10 s first stage). On `medium-l75-building-s1` and `-building-s2` stage 1 ends at its time limit and later stages get no time. The spec split 10/10/3/3/2/2 is unchanged. Options:
1. A separate medium time tier in the spec (my recommendation). Presolve alone makes a 10 s first stage unrealistic at this size.
2. Leave medium out of the frozen set and evaluate on the 12 small ones.
3. One more shrinking round on R2 (room-slot at-most-one groups; leaving R2 out saved about 2 s of presolve on `hold-s2`) before deciding.
Medium is frozen in a later commit only if joint returns a plan on all 12.

## Separate defect: greedy is slow
Greedy takes up to 437 s on medium (`medium-l75-building-s1`; 230 s on `-building-s2`). Cause: it calls `validate()` on the whole timetable for each of its 205 candidate steps, and 80% of that is the pairwise loop in R6's `check` (38 million `shares_person` calls). Fix idea: index `check` by person and process pairs in the same order so the violations list is identical. Keep greedy time out of joint time comparisons; `joint` now runs greedy first (its plan is the start hint).

## Environment (Windows)
- `export PATH="$HOME/.local/bin:$PATH"` for uv. gh is at "C:\Program Files\GitHub CLI\gh.exe" (sohanroy676).
- Write files as UTF-8 without BOM and LF; use the Write tool for long files.
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do not push or merge without approval. After a push, watch CI with Monitor (`gh pr checks`), report every terminal state including `secrets`, and do not report green unless seen.
- A Monitor expires after 30 minutes at most and does not stop a script started with `nohup`; for long runs write to a log and watch the log. Do not run two timed jobs at once (they share the CPU and can fail a time-limited solve).
- The full suite takes about 5.5 minutes (the two golden equivalence suites are about 4 minutes of that).

## Open items, in order
1. The medium decision above (and the greedy `check` fix if the user wants it).
2. Spec assumptions 1-24 in `docs/model-spec.md` section 7 still need the user's confirmation (3 and 19 are resolved). Go through them with the user.
3. Housekeeping: projectBrief says about 400 scenarios, ROADMAP says 100+ for Gate 2; agree one number with the user.
4. Then: ITC 2019 loader (waits for the user's data files), sequential and re-solve baselines, eval harness and stats (Gate 2), repair-overrun loop and approval triggers, contract-net.

## Known facts that matter
- Medium models: 29k to 116k constraints, 1.0 to 2.4 s build, presolve 1.9 to 5.0 s on the five scenarios that had no plan. Each presolve pass probes every Boolean, so cost follows the number of Booleans and at-most-one groups, not the constraint count.
- `DecisionVars` now has shared literals (`any_happens`, `building_start_literals`, `start_literals`, `placed_literal`, `start_bounds`). They are "implied by" literals except `placed_literal` (it implies a placement). Use them in a rule only in the direction that fits.
- `stage_expression(ctx, i)` builds one stage's helper variables; `stage_expressions(ctx)` still returns all six (tests use it).
- Changing the output for a given seed means bumping `GENERATOR_VERSION`.
