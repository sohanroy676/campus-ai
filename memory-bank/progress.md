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

- Model spec, domain schemas and hard-rule library on `feature/model-spec-schemas` (6 commits, not pushed) — 2026-10-29
  - `docs/model-spec.md` (time model, variables, R1 to R8, objective C/P/D/K/T, solver settings, 12 numbered assumptions) and ADR 0002
  - `domain/`: time (30-min slots, Mon to Fri 08:00 to 18:00), entities, events, plan, problem
  - `rules/`: R1 to R8, each with a `check` and a CP-SAT `post` built on shared predicates in `_shared.py`; `variables.py` (decision variables and assumption literals), `registry.py`, `validator.py`
  - 219 tests: unit, Hypothesis properties, and check/encoding agreement tests (validator verdict equals CP-SAT feasibility). `rules/` coverage is about 100%
  - Checked locally: `ruff check`, `ruff format --check`, `mypy src` and `uv run pytest` all pass

## In progress

- Branch `feature/model-spec-schemas` awaits review. Push, PR and CI only with approval.

## Next

- Confirm the spec assumptions in `docs/model-spec.md` section 7 (especially 3: equipment source contention).
- Re-check the gitleaks `secrets` job on the first PR (valid commit range).
- Remaining ROADMAP "Now" items: officer and facilities interviews, event-log simulator, greedy baseline, first CP-SAT model (lexicographic stages and objective, built on `rules.variables`).
