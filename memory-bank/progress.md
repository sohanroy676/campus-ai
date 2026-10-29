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

## In progress

- Nothing in progress. Next: the seeded generator on a new branch (ask the user for inputs first).

## Next

- Confirm the other spec assumptions in `docs/model-spec.md` section 7.
- Remaining ROADMAP "Now" item: officer and facilities interviews.
- v0.3 to v0.5 (ROADMAP "Next"): seeded generator (synthetic first, ITC 2019 loader when the data files exist), repair-overrun re-planning loop (re-run `derive_recovery` on the state), approval triggers, sequential and re-solve baselines.
