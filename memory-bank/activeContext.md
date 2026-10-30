# Active Context

<!-- Update this at the end of every session. This is the first thing to read when resuming. -->

## Current focus
Work is on `feature/frozen-grid` (from `main` d179f78), pushed to `origin/feature/generator` (the designated branch for this environment; no PR opened). Done: 270 of 405 frozen (135 small, 135 medium; loads 50/75/90, seeds 1 to 15), R1 and R2 `check` indexed (greedy 3.6x faster on the slowest medium), timing record in `docs/results/solver-timing-2026-10-30.md`. Open: (1) joint has not been run on the 246 newly frozen scenarios; (2) large has no time tier: on 9 large scenarios with the medium tier joint gave a plan on 7 and none on `large-l75-building-s1` and `large-l90-room-s1` (presolve about 15 s), proposed 60/60/18/18/12/12 s, awaiting the user's go-ahead; nothing large is frozen. Merged feature branches still exist; do not delete them. Gate 1 is reached: `smartcampus run <scenario> --method joint|greedy` works end to end. CI on `main` d179f78 was green (`checks`, `secrets`).

## Recent decisions
- The scaffold is merged and pushed (`origin/main` at b56e88c). `feature/project-scaffold` still exists; do not delete it.
- CI on that first push: `checks` passed. `secrets` (gitleaks) failed falsely: the push held a root commit, so the range `765732d^..b56e88c` did not exist and 0 bytes were scanned. Not a leak. `ci.yml` is deliberately unchanged. The first PR from this branch is the first real test of the secrets job.
- Model spec inputs are settled and written into `docs/model-spec.md`: 30-minute slots, Mon to Fri, 08:00 to 18:00 (20 slots a day, 100 a week), lexicographic objective C, P, D, K, S, T.
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
- Event log: state version = number of events; an event's `version` must equal it, and `PlanApplied.plan.based_on_version` must equal it too (ADR 0003). `run` replaces the log at `--db` (default `var/campus.db`) but refuses to touch a file that is not an event store.
- Greedy handles classes by original start and takes the cheapest valid placement by P, D, K, S, T; it validates each step with `rules.validator` and treats unhandled classes as cancelled. Do not add rule logic there.
- Long shell heredocs failed in Bash here; write multi-line files with the Write tool.

## Blockers / open questions
- Spec assumptions 1 to 24 are confirmed by the user (2026-10-30). Scenario count is settled: the frozen v1.0 evaluation set is 405 instances (20 smoke instances are separate and not counted); 24 are frozen so far.
- Decisions for `impact/`: window = plan time (or first affected day start) to the end of the last affected day; affected = overlap a fault or hold; movable = affected plus not-yet-started classes in the window within 10 minutes' walk; faults and holds are clipped to plan time (assumptions 21 to 24, still to confirm). Approval triggers (spec section 6) are not built: `run` applies the plan directly.

## Next step
ITC 2019 loader (needs the data files), sequential and re-solve baselines, eval harness and stats (Gate 2), recovery loop with approval triggers, contract-net. Possible: speed up R2/R1 `check` (greedy is still about 112 s on the slowest medium). Push and PR only with approval; watch CI with Monitor (include the secrets job).
