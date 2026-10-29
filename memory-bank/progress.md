# Progress

<!-- Running log. Append, don't rewrite history. Newest at top.
     This tracks WORK STATUS (agent-facing, session to session).
     For the forward-looking feature plan, see ROADMAP.md instead —
     don't duplicate the full plan here, just what's actually in motion. -->

## Done

- Project scaffold on `feature/project-scaffold` (commit a980f04) — 2026-10-29
  - uv project: Python 3.12, deps from tech-stack.md, ruff + mypy config (strict for rules/solver/sim), `uv.lock` committed
  - `src/smartcampus/` package tree from architecture.md (empty packages with docstrings)
  - Typer CLI stub (`generate`, `run`, `compare`, `eval`); each exits 1 with "not implemented yet"
  - `tests/{unit,property,golden}/` with a CLI smoke test; `.env.example` with `LLM_ENABLED=false`
  - Checked locally: `uv sync --frozen`, `uv run pytest` (6 passed), `ruff check`, `ruff format --check`, `mypy src` all pass
- Docs, agent rules and CI config under version control (commit 765732d) — 2026-10-29

## In progress

- Scaffold is awaiting review. Plan: fast-forward merge into `main`, then push to GitHub. Not pushed yet, so CI has not run.

## Next

- Model spec (decision variables, 8 hard rules, lexicographic objective) and Pydantic schemas (ROADMAP "Now").
