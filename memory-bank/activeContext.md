# Active Context

<!-- Update this at the end of every session. This is the first thing to read when resuming. -->

## Current focus
Model spec and Pydantic schemas on `feature/model-spec-schemas`: spec doc and ADR 0002 first, then `domain/` (time, entities, events, plan, problem), then `rules/` (R1 to R8, each written once with a validator check and a CP-SAT encoding).

## Recent decisions
- The scaffold is merged and pushed (`origin/main` at b56e88c). `feature/project-scaffold` still exists; do not delete it.
- CI on that first push: `checks` passed. `secrets` (gitleaks) failed falsely: the push held a root commit, so the range `765732d^..b56e88c` did not exist and 0 bytes were scanned. Not a leak. `ci.yml` is deliberately unchanged. The first PR from this branch is the first real test of the secrets job.
- Model spec inputs are settled: 30-minute slots, Mon to Fri, 08:00 to 18:00 (20 slots a day, 100 a week), lexicographic objective C, P, D, K, T. Full wording goes into `docs/model-spec.md`.
- Extras `api` (FastAPI, Uvicorn) and `llm` (OpenAI SDK) are optional, not core dependencies, because they only matter from v0.5 or as a stretch goal.
- mypy has no per-module `strict = true`, so the strict flags are listed one by one in the overrides for `rules`, `solver` and `sim`.
- Tooling on this Windows machine: uv 0.13.6 is in `~/.local/bin` (add to PATH per session). `git-cliff` runs via `uvx git-cliff --config cliff.toml -o CHANGELOG.md`. `gh` is at `C:\Program Files\GitHub CLI\gh.exe` (authenticated as sohanroy676, scopes repo and workflow) and may not be on PATH.
- Write files as UTF-8 without BOM and with LF. A BOM in `__init__.py` made `ruff format --check` panic, and a BOM in `.env.example` would corrupt its first key.
- Repo-local git identity is set to sohanroy676.

## Blockers / open questions
- None. Assumptions made while reading the spec are listed in `docs/model-spec.md` (once written) and need the user's confirmation.

## Next step
Write the spec doc and ADR, then `domain/`, then `rules/`. Push and open a PR only with approval, then watch CI with Monitor (include the secrets job).
