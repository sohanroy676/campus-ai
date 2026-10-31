# Progress

<!-- Running log. Append, don't rewrite history. Newest at top.
     This tracks WORK STATUS (agent-facing, session to session).
     For the forward-looking feature plan, see ROADMAP.md instead —
     don't duplicate the full plan here, just what's actually in motion. -->

## Done

- Project scaffold merged to `main` and pushed (a980f04, docs commit b56e88c on `origin/main`) — 2026-10-29
  - uv project: Python 3.12, deps from tech-stack.md, ruff + mypy config (strict for rules/solver/sim), `uv.lock` committed
  - `src/smartcampus/` package tree from architecture.md (empty packages with docstrings)
  - Typer CLI stub (`generate`, `run`, `compare`, `eval`); each exits 1 with "not implemented yet"
  - `tests/{unit,property,golden}/` with a CLI smoke test; `.env.example` with `LLM_ENABLED=false`
  - Checked locally: `uv sync --frozen`, `uv run pytest` (6 passed), `ruff check`, `ruff format --check`, `mypy src` all pass
- Docs, agent rules and CI config under version control (commit 765732d) — 2026-10-29
- CI on the first push: `checks` passed. `secrets` (gitleaks) failed falsely on the root-commit range (0 bytes scanned, not a leak); `ci.yml` left unchanged by decision.

- Model spec, domain schemas and hard-rule library on `feature/model-spec-schemas` (merged to `main` and pushed, 0d49964; CI green: `checks` and `secrets`) — 2026-10-29
  - `docs/model-spec.md` (time model, variables, R1 to R8, objective C/P/D/K/T, solver settings, 12 numbered assumptions) and ADR 0002
  - `domain/`: time (30-min slots, Mon to Fri 08:00 to 18:00), entities, events, plan, problem
  - `rules/`: R1 to R8, each with a `check` and a CP-SAT `post` built on shared predicates in `_shared.py`; `variables.py` (decision variables and assumption literals), `registry.py`, `validator.py`
  - 219 tests: unit, Hypothesis properties, and check/encoding agreement tests (validator verdict equals CP-SAT feasibility). `rules/` coverage is about 100%
  - Checked locally: `ruff check`, `ruff format --check`, `mypy src` and `uv run pytest` all pass

- R4 source contention and the lexicographic solver on `feature/solver-stages` (merged and pushed, `main` = `origin/main` = 18b6c4b; CI green: `checks` and `secrets`) — 2026-10-29
  - R4: a moved unit is unavailable at its source until the borrowing class ends plus the return trip (same time as outbound; availability only, no mover, no K cost); per (room, type) stock check, check and CP-SAT encoding in agreement
  - `solver/objective.py`: `StageValues` (C, P, D, K, S, T), `evaluate()` reference score, `stage_expressions()`
  - `solver/solve.py`: `solve()` runs the five stages (10/10/4/4/2 s, workers 1, seed 42), validates the plan; `solver/explain.py` names conflicting rules for bad input
  - 279 tests; brute-force property test shows the solver's result equals the best valid plan; mutation probes catch dropped constraints. `rules/` and `solver/` coverage about 100%
  - Checked locally: `ruff check`, `ruff format --check`, `mypy src`, `uv run pytest` all pass

- Gate 1: one scenario runs end to end, baseline included, on `feature/sim-and-greedy` (merged as PR #4, `main` = bafcbe8; CI green: `checks` and `secrets`) — 2026-10-29
  - Objective: stage S (start shift, minutes from the original start, both directions) between K and T, so the order is C, P, D, K, S, T and the budget is 10/10/3/3/2/2 s. Resolves assumption 19 (20 unchanged); spec section 4, ADR 0002 updated
  - `sim/`: SQLite event store (`store.py`) with append-only triggers, dense versions from 0, stale `PlanApplied` rejected, clock never backwards; pure reducer and `SimState` (`state.py`); ADR 0003. `EventStore.create_fresh` replaces only an earlier event store
  - `generator/scenario.py`: scenario = serialized `RecoveryProblem` (canonical JSON, `ScenarioError` naming the field); `scenarios/dev/ac-failure.json` is the demo
  - `baselines/greedy.py`: classes by original start, each takes the cheapest valid placement by P, D, K, S, T (shared cost functions, `move_cost`), cancels if none fits
  - `coordinator/run.py`, `reporting/summary.py`, CLI `smartcampus run <scenario> --method joint|greedy [--report] [--db]`; exit codes 0 ok, 1 no plan, 2 bad input, 3 internal
  - Demo result (golden test): joint scores people moved 26, greedy 55 (greedy puts `ml-lab` at 10:00 in AI-Lab-02 and then has to move `net-lab`)
  - 388 tests; coverage 99% overall, 100% for `sim/`, `baselines/`, `coordinator/`, `reporting/`, `generator/`. `ruff`, `mypy src`, `uv run pytest` pass

- `impact/` on `feature/impact-and-generator` (merged as PR #5; CI green: `checks` and `secrets`) — 2026-10-29
  - `impact/derive.py`: `assess()` and `derive_recovery()` give the window (plan time or first affected day start, to the end of the last affected day), the affected classes (overlap a clipped fault or hold; equipment holds hit classes needing that type in the pool's room) and the movable set (affected plus not-yet-started classes in the window within 10 minutes' walk). Faults and holds are clipped to plan time. Spec assumptions 21 to 24
  - Scenario files may omit both `window` and `movable_activity_ids` (one without the other is an error); the demo gives the same scores either way
  - 420 tests, coverage 99% overall and 100% for `impact/`; property tests: derivation is idempotent, no fixed class is left inside a disruption, and a sound timetable stays solvable after any disruption

- Seeded synthetic generator (merged as PR #6) — 2026-10-29
  - `generator/synth.py`: `generate_scenario(size, load, severity, seed)`; sizes small/medium/large, load 10 to 95, severity room/building/hold; `provenance` (generator version, seed, parameters) in the scenario file and in the run report; CLI `smartcampus generate`
  - Spec section 8. 451 tests, coverage 99%

- Frozen small set, R6 re-encoding and greedy start plan on `feature/frozen-set` (merged as PR #7) — 2026-10-30
  - `scenarios/frozen/` holds the 12 small scenarios (size small x load 50, 75 x room/building/hold x seeds 1, 2); `tests/golden/test_frozen_set.py` regenerates each byte for byte. The 12 medium files are in `scenarios/candidates/medium/`, not frozen
  - Clean run of all 24 (nothing else running): greedy solves all 24; joint solves all 12 small and 7 of 12 medium. Joint's no-plan cases: `medium-l50-building-s2`, `medium-l75-building-s1`, `-hold-s2`, `-room-s1`, `-room-s2`
  - Cause (ADR-0004): R6 looked at every pair of options, about 285 s to build and 1.87M constraints; presolve (about 18 s) used up the 10 s first stage. Fix: R6 grouped by person, time and building (build 3 to 7 s, 160k to 560k constraints); `tests/golden/test_r6_encoding.py` compares it with the old pairwise encoding on all 24 scenarios
  - `solve(..., hint=plan)`; `run_scenario` passes the greedy plan for `joint`
  - After the change, joint returns a plan on `medium-l50-building-s2` but not on the other four. Presolve is still 6 to over 10 s on medium. Greedy takes 23 to 435 s there
  - 491 tests; `ruff`, `mypy src`, `uv run pytest` pass (the full suite takes about 4 minutes)

- Smaller models for R4, R5, R6 and the objective on `feature/frozen-set` (merged as PR #7) — 2026-10-30
  - Shared per-class literals and start bounds (`DecisionVars`), R4/R5 rewritten on them, objective helpers built stage by stage (`stage_expression`). `tests/golden/test_equipment_encoding.py` checks old vs new vs validator on all 24 scenarios; existing agreement tests unchanged
  - Medium models went from 160k to 560k constraints to 29k to 116k; presolve on the 5 failing scenarios is 1.9, 2.8, 5.0, 2.4 and 4.3 s (gate was under 5 s). Gate run on all 12 medium: joint returns a plan on 10; no plan on `medium-l75-hold-s2` and `medium-l75-room-s2`. ADR-0004 has the table
  - Greedy takes up to 437 s on medium because `validate()` runs the pairwise R6 `check` for each of its 205 steps (separate defect, not fixed)
  - 515 tests, `ruff`, `mypy src` pass; the full suite takes about 5.5 minutes

- Medium time tier and faster greedy on `feature/medium-tier` (2 commits, not pushed) — 2026-10-30
  - `SolverSettings.for_problem`: small 10/10/3/3/2/2 s, medium and large 30/30/9/9/6/6 s (spec section 5, ADR 0005). Joint returns a plan on all 12 medium scenarios; the 12 files moved to `scenarios/frozen/` (24 frozen)
  - R6 `check` indexed by person and swept by start, same violations and order (golden test vs the old loop); greedy on `medium-l75-building-s1` 437 s to about 112 s (rest is the R2 and R1 checks)
  - 543 tests pass (about 7 min); `ruff`, `mypy src` pass

- Frozen grid, faster greedy and timing record on `feature/frozen-grid` (pushed to `origin/feature/generator`) — 2026-10-30
  - Joint run on medium load 90 (6 scenarios) returned a plan on all 6, so load 90 stays in the 405; spec section 8 updated. No per-load tier
  - `scenarios/frozen/` now 270 files: small and medium x loads 50/75/90 x room/building/hold x seeds 1 to 15 (135 each). `GENERATOR_VERSION` still "1"; the 24 earlier files are unchanged. `test_frozen_set.py` checks the grid and regenerates each byte for byte. The old-encoding golden tests (`test_r6_encoding`, `test_equipment_encoding`, `test_r6_check_index`) stay on the original 24 (12 small for the last)
  - Joint has NOT been run on the 246 new frozen scenarios (small load 90, seeds 3 to 15 everywhere, medium load 90 seeds 3 to 15). Do that before the 405 runs; report any no-plan
  - R1 and R2 `check` indexed (same violations, same order; `tests/golden/test_r1_r2_check_index.py`); greedy on `medium-l90-building-s1` 321 s to 89.5 s
  - Large measured on 9 scenarios (seed 1) with the medium tier: plan on 7, no plan on `large-l75-building-s1` and `large-l90-room-s1` (presolve about 15 s). No large tier chosen, no large frozen
  - All timings in `docs/results/solver-timing-2026-10-30.md` and `.csv`
  - 801 tests pass (about 7 min); `ruff`, `mypy src` pass

- Joint check on the newly frozen scenarios (commit b9f0c44) — 2026-10-30
  - 240 scenarios (the 246 minus 6 medium load 90 seed 1 and 2 timed earlier), greedy then joint, one job at a time, `num_workers=1`, seed 42, with the greedy hint. Plan on 229, no plan on 11, all medium (5 at load 75, 6 at load 90; 5 hold, 5 room, 1 building); small had none
  - Times: small greedy median 0.9 s (max 23.3), joint median 2.1 s (max 31.6); medium greedy median 2.8 s (max 184.7), joint median 23.0 s (max 95.9)
  - Each no-plan ended after 32.4 to 33.9 s (about the 30 s first stage plus build); cause not verified. No per-load tier added. Results in `docs/results/frozen-joint-check-2026-10-30.md` and `.csv`

- Hint fix, large tier, baselines and eval harness on `feature/frozen-grid` (commits abfb433, dfc15db, 2177c64, bc5c265, c6e7ced; local, not pushed) — 2026-10-30
  - Medium no-plans: the hint covered 63k of 88k variables, so CP-SAT found no first solution in 30 s; `_complete_hint` fixes it. All 11 former no-plans return a plan on the medium tier; the two large seed-1 failures too. `docs/results/medium-no-plan-diagnosis-2026-10-30.md`, ADR 0006
  - Large tier 60/60/18/18/12/12 s (pilot on seeds 101 to 103 plus seed 1: plan on 5 of 5 on both tiers; the longer tier lowers people moved on 3 of 5). 135 large scenarios frozen: `scenarios/frozen/` = 405 files (47 MB of large JSON)
  - Baselines: `baselines/resolve.py` (P, D, S dropped, freed time to C and K, no hint) and `baselines/sequential.py` (rooms, equipment, timing as restricted solves); `Method.RESOLVE`, `Method.SEQUENTIAL`; spec section 9
  - Eval: `eval/metrics.py`, `harness.py`, `stats.py`, `report.py`; `smartcampus eval` (resumable `results.jsonl`, `report.md`) and `compare`; spec section 10. Smoke run on 6 small scenarios x 4 methods: plan on all 24
  - 989 tests pass (about 8.5 min); `ruff`, `mypy src` pass

- Repair-overrun loop and approval triggers on `feature/recovery-loop` (from `feature/frozen-grid`; local, not pushed) - 2026-10-30
  - `coordinator/approval.py` (`triggers`), `replan.py` (`replan_problem`: applied plans folded in, plan time = log clock, earlier moves in `prior_moves_this_week`, touched unstarted classes recoverable again), `followups.py`, `loop.py` (`recover`), `run.plan_with_method` (planning step moved out of `run_scenario`, behaviour unchanged)
  - Approval is a field on `PlanApplied` (`Approval`), not its own event (it would stale the plan); deviation from the plan the user saw, reason in ADR 0008. Spec section 6 extended
  - CLI `smartcampus cascade <scenario> --followups <file> [--auto-approve/--no-auto-approve]`; demo `scenarios/dev/ac-cascade.json` (the AC demo plus `robotics-lab`) and `ac-cascade-overrun.json`; saved output `docs/results/cascade-demo-2026-10-30.txt`
  - Tests: `tests/unit/test_approval.py`, `test_loop.py`

- Contract-net on `feature/recovery-loop` (local, not pushed) - 2026-10-30
  - Spec section 9 (user chose: re-auction with strict whole-plan improvement, 5 rounds plus the tier's wall-clock limit, initial order by original start). `agents/equipment.py` (`propose_moves`, moved out of greedy), `agents/resource.py` (`Bid`, `bid_cost`, `RoomAgent`), `agents/contract_net.py` (`contract_net`); `Method.CONTRACT_NET` ("contract_net"), in the CLI and the eval report order
  - Extension to the shown definition: a class with no bid may ask the few awarded classes the validator names most often to step aside (displacement), because plain re-bidding cannot rescue a cancelled class; classes without an award go first in each round
  - Initial auction equals greedy (same order, same costs), so the result is never worse than greedy unless the limit ends the auction early. Seen: small load 90 hold seed 2 cancellations 2 to 1; `small-l75-building-s1` P 2249 to 2101 but still 5 cancellations (joint 2), 30 s limit used
  - `tests/unit/test_contract_net.py`

- Eval records stamped on `feature/recovery-loop` (local) - 2026-10-30
  - `RunRecord` gains `commit` (`code_version()`, "+dirty" if tracked files differ), `generator_version`, `stage_seconds`, `num_workers`, `random_seed` (defaults keep older records loadable; greedy has no settings). The report names the code and warns on mixed commits or unstamped runs, and the threats list now includes contract-net's wall-clock limit
  - Start the final run from a clean tree and an empty `results/` so one commit covers every record

- Contract-net subset check (not a result; 14 frozen instances: 6 small, 4 medium, 4 large; greedy and contract_net; commit a7f4f75; files in gitignored `var/cn-out/`) - 2026-10-30: plan on 28 of 28. Contract-net was better than greedy on 9, equal on 5, worse on none (lexicographic). It hit its time cap on 5 (large-l90-building-s1 180 s, medium-l75-building-s1 and medium-l90-hold-s1 90 s, small-l75-building-s1 and small-l90-building-s1 30 s). Largest gain: large-l90-building-s1 cancellations 5 to 1. Median time 28.8 s against greedy 6.0 s. Joint not run on the subset

- Large one-seed-per-cell check (not a result; `docs/results/large-check-2026-10-31.md`, CSV beside it) - 2026-10-31
  - 9 large seed-2 instances: greedy and joint plan on 9 of 9 (joint 46 to 402 s, slowest `large-l90-building-s2`); resolve, sequential, contract_net on the 3 load-90 ones (status plan on all)
  - Found: resolve cancels 289 of 289 (building) and 128 (room) while status is `plan`; contract_net on `l90-building` hit its 180 s cap before greedy's own 192 s auction ended, so C104 against greedy C0
  - Open: contract-net cap on large; how to count and whether to hint resolve on large. Decisions asked of the user via Claude desktop

- Pre-freeze changes on `feature/freeze-prep` (from main 0501b34; local, not pushed) - 2026-10-31
  - ADR 0009: contract-net's wall-clock limit (30/90/180 s) starts after its first auction (`run_contract_net`, `AuctionResult`); ADR 0010: resolve gets the greedy start-plan hint. Spec 5, 9, 10 updated
  - Records: `limit_hit`, `start_unimproved` (vs the greedy plan, greedy runs first per instance); `eval/manifest.py` writes `manifest.json` (commit, CPU, OS, Python, OR-Tools, NumPy, SciPy) and refuses a resume under another commit/environment. Report: counts per method and size, wall time beside stage seconds, primary (joint vs sequential on C and P, Holm over the two) and secondary (one Holm family per section, with median difference and win rate), new threats text
  - Greedy: `fixed_placements` cached by identity and `Placement.end/slots` cached (`rules/_shared.py`); R1/R2 `check` were already indexed, the profile showed fixed placements rebuilt 70546 times. `large-l90-building-s2` 192 s to 105 s. Plans identical on 29 golden instances (`tests/golden/test_greedy_unchanged.py`, `data/greedy/`)
  - `scenarios/smoke/`: 20 instances (10 small, 8 medium, 2 large; seeds 201 to 220), `tests/golden/test_smoke_set.py`
  - Large re-check (`docs/results/large-recheck-2026-10-31.md`): contract-net C0 on `l90-building` (was C104), resolve C0 on all three (was C289 and C128); contract-net equals greedy on all three
  - ADR 0007 updated: time estimate about 20 h (26 to 30 h if large is everywhere as slow as load 90; the expected "more than 36 h" is not supported by the measurements), run-safety checklist, mid-run bug policy

- Live demo dashboard on `claude/project-thread-ennlph` (PR to main) - 2026-10-31
  - `api/demo.py` (`DemoSession`: incidents and plans as events in an in-memory log, proposals from `plan_with_method`, agent activity recorded from the real steps), `api/app.py` (FastAPI, one worker thread), `api/static/` (one page, plain JS, offline), CLI `smartcampus demo`
  - Six panels: Campus Overview, Incident Panel, Agent Activity, Solution Comparison, Updated Campus State, Performance Metrics; scenarios `ac-failure`, `ac-cascade`, `generated-small` (small, load 75, room, seed 2: joint 38 people moved, greedy 109)
  - ADR 0011, `docs/demo.md`; tests `tests/unit/test_api_demo.py`, `test_api_app.py` (real uvicorn server + urllib; Starlette's TestClient would need another package)

## In progress

- Next: the cheap checks (about 20 instances for contract-net, one seed per cell), then the freeze and the full run (ADR 0007).

## Next

- Contract-net; then the one-seed-per-cell check, then (code frozen) the full evaluation run, results and stats into `docs/results/`; report plan rate per method and per size, the paired Wilcoxon on instances both solved, and the sensitivity view.
- Officer and facilities interviews (ROADMAP "Now").
- ITC 2019 loader when the data files exist; repair-overrun re-planning loop, approval triggers, contract-net (v0.3 to v0.5).
