# Active Context

<!-- Update this at the end of every session. This is the first thing to read when resuming. -->

## Current focus
`feature/sim-and-greedy`: assumption-19 tie-break, the `sim/` event store, the scenario loader, the greedy baseline and CLI `run` (Gate 1). `main` = `origin/main` = 18b6c4b, CI green. It holds `domain/`, `rules/` R1 to R8 (R4 with source-side equipment contention) and `solver/` (objective, `solve()`, infeasibility explanation).

## Recent decisions
- The scaffold is merged and pushed (`origin/main` at b56e88c). `feature/project-scaffold` still exists; do not delete it.
- CI on that first push: `checks` passed. `secrets` (gitleaks) failed falsely: the push held a root commit, so the range `765732d^..b56e88c` did not exist and 0 bytes were scanned. Not a leak. `ci.yml` is deliberately unchanged. The first PR from this branch is the first real test of the secrets job.
- Model spec inputs are settled and written into `docs/model-spec.md`: 30-minute slots, Mon to Fri, 08:00 to 18:00 (20 slots a day, 100 a week), lexicographic objective C, P, D, K, T.
- Each rule is `check` + `post` over shared predicates (`rules/_shared.py`). `tests/property/test_rule_agreement.py` and `tests/unit/test_rule_encodings.py` assert the validator verdict equals CP-SAT feasibility. Do not edit one side without the other.
- Solver: `solve(problem, SolverSettings())`; tests pass small `stage_seconds`. `stage_expressions` and `evaluate` share per-placement cost functions in `solver/objective.py`; `tests/property/test_objective_props.py` asserts they agree. Hint each CP-SAT variable once (a duplicate hint makes the model invalid).
- ortools 9.15: use the snake_case API (`new_bool_var`, `add`, `only_enforce_if`, ...). The CamelCase methods are untyped and fail strict mypy.
- Plans may be malformed on purpose (both assigned and cancelled, unknown ids) so R1 and R4 can report them; the schema does not reject those.
- Test helpers live in `tests/builders.py`, `tests/cp_helpers.py` and `tests/property/strategies.py` (`pythonpath` set in `pyproject.toml`).
- Extras `api` (FastAPI, Uvicorn) and `llm` (OpenAI SDK) are optional, not core dependencies, because they only matter from v0.5 or as a stretch goal.
- mypy has no per-module `strict = true`, so the strict flags are listed one by one in the overrides for `rules`, `solver` and `sim`.
- Tooling on this Windows machine: uv 0.13.6 is in `~/.local/bin` (add to PATH per session). `git-cliff` runs via `uvx git-cliff --config cliff.toml -o CHANGELOG.md`. `gh` is at `C:\Program Files\GitHub CLI\gh.exe` (authenticated as sohanroy676, scopes repo and workflow) and may not be on PATH.
- Write files as UTF-8 without BOM and with LF. A BOM in `__init__.py` made `ruff format --check` panic, and a BOM in `.env.example` would corrupt its first key.
- Repo-local git identity is set to sohanroy676.

## Blockers / open questions
- Assumptions in `docs/model-spec.md` section 7 (1 to 20) still need the user's confirmation, except 3 (resolved by extending R4) and 19 (resolved: add a tie-break for distance from the original start, after T; 20 stays as is).
- Decisions for this branch: scenario file is a serialized `RecoveryProblem` with explicit `window` and `movable_activity_ids` (`impact/` deferred); event `version` is a dense counter from 0 and a `PlanApplied` built on an older version is rejected as stale.

## Next step
Finish `feature/sim-and-greedy`, then push and open a PR only with approval and watch CI with Monitor (include the secrets job).
