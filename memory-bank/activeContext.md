# Active Context

<!-- Update this at the end of every session. This is the first thing to read when resuming. -->

## Current focus
Project scaffold is finished on `feature/project-scaffold` and waiting for review. After approval it is merged to `main` (fast-forward) and pushed.

## Recent decisions
- CI only triggers on push/PR to `main`, so the chosen path is merge to `main` first, then push, then watch CI with Monitor.
- Extras `api` (FastAPI, Uvicorn) and `llm` (OpenAI SDK) are optional, not core dependencies, because they only matter from v0.5 or as a stretch goal.
- mypy has no per-module `strict = true`, so the strict flags are listed one by one in the overrides for `rules`, `solver` and `sim`.
- Tooling on this Windows machine: uv 0.13.6 is in `~/.local/bin` (add to PATH per session). `git-cliff` runs via `uvx git-cliff` with the repo's `cliff.toml`. `gh` is not installed yet.
- Write files as UTF-8 without BOM and with LF. A BOM in `__init__.py` made `ruff format --check` panic, and a BOM in `.env.example` would corrupt its first key.
- Repo-local git identity is set to sohanroy676.

## Blockers / open questions
- `gh` must be installed and authenticated before CI can be watched (`winget install GitHub.cli`, then `gh auth login`).
- For the model spec I need: the 8 hard rules, slot granularity (length of a slot and the day/week span), the objective weights and the tie-break.

## Next step
Get approval, merge and push the scaffold, watch CI. Then start the model spec and Pydantic schemas (`domain/`, then `rules/`).
