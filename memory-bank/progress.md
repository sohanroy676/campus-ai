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

## In progress

- Model spec and schemas on `feature/model-spec-schemas`: spec doc, ADR 0002, `domain/`, `rules/` R1 to R8 with tests.

## Next

- Re-check the gitleaks `secrets` job on the first PR (valid commit range).
- Remaining ROADMAP "Now" items: officer and facilities interviews, event-log simulator, greedy baseline, first CP-SAT model.
