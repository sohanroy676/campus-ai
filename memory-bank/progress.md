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

- R4 source contention and the lexicographic solver on `feature/solver-stages` (5 commits, not pushed) — 2026-10-29
  - R4: a moved unit is unavailable at its source until the borrowing class ends plus the return trip (same time as outbound; availability only, no mover, no K cost); per (room, type) stock check, check and CP-SAT encoding in agreement
  - `solver/objective.py`: `StageValues` (C, P, D, K, T), `evaluate()` reference score, `stage_expressions()`
  - `solver/solve.py`: `solve()` runs the five stages (10/10/4/4/2 s, workers 1, seed 42), validates the plan; `solver/explain.py` names conflicting rules for bad input
  - 279 tests; brute-force property test shows the solver's result equals the best valid plan; mutation probes catch dropped constraints. `rules/` and `solver/` coverage about 100%
  - Checked locally: `ruff check`, `ruff format --check`, `mypy src`, `uv run pytest` all pass

## In progress

- `feature/solver-stages` awaits review. Push, PR and CI only with approval.

## Next

- Decide spec assumption 19: equal-cost start times (the solver may pull classes earlier) and whether to add a tie-break for distance from the original start.
- Confirm the other spec assumptions in `docs/model-spec.md` section 7.
- Remaining ROADMAP "Now" items: officer and facilities interviews, event-log simulator, greedy baseline, CLI `run` end to end (needs a scenario loader).
