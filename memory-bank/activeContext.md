# Active Context

<!-- Update this at the end of every session. This is the first thing to read when resuming. -->

## Current focus
Work is on `feature/frozen-set` (from `origin/main` after PR #6; 3 commits plus a docs commit, not pushed). Frozen set = the 12 small scenarios; the 12 medium files are candidates in `scenarios/candidates/medium/`, frozen later only if joint returns a plan on all 12. Merged feature branches still exist; do not delete them. Gate 1 is reached: `smartcampus run <scenario> --method joint|greedy` works end to end.

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
- Assumptions in `docs/model-spec.md` section 7 (1 to 20) still need the user's confirmation, except 3 (resolved by extending R4) and 19 (resolved: new stage S, distance from the original start, between K and T; 20 stays as is). A stage placed after T would not have fixed 19, because T already prefers the lower room index.
- Decisions for `impact/`: window = plan time (or first affected day start) to the end of the last affected day; affected = overlap a fault or hold; movable = affected plus not-yet-started classes in the window within 10 minutes' walk; faults and holds are clipped to plan time (assumptions 21 to 24, still to confirm). Approval triggers (spec section 6) are not built: `run` applies the plan directly.

## Next step
Report the medium result to the user and get a decision before touching solver settings. Facts (ADR-0004): after the R6 re-encoding and the greedy start plan, joint solves `medium-l50-building-s2` but not `medium-l75-building-s1`, `-hold-s2`, `-room-s1`, `-room-s2`. Build time is now 3 to 7 s but presolve is 6 to over 10 s, longer than the 10 s first stage; the spec's 10/10/3/3/2/2 split is unchanged. Other constraints still large: R4, R5 and the objective expressions (160k to 560k constraints). Greedy takes 23 to 435 s on medium and now runs before joint.
Then: confirm spec assumptions 1 to 24 with the user, regenerate CHANGELOG.md, ITC 2019 loader (needs the user's data files), sequential and re-solve baselines, eval harness and stats (Gate 2), the recovery loop with approval triggers, contract-net. Push and PR only with approval; watch CI with Monitor (include the secrets job).
