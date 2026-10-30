# Active Context

<!-- Update this at the end of every session. This is the first thing to read when resuming. -->

## Current focus
Work is on `feature/frozen-grid` (from `main` d179f78), pushed to `origin/feature/generator` up to fe13523; the commits since (abfb433, dfc15db, 2177c64, bc5c265, c6e7ced) are local and NOT pushed. No PR. Done this session: (a) the 11 medium no-plans were a hint defect (hint covered only decision variables, so CP-SAT could not complete it); fixed with `_complete_hint`, all 11 now return a plan on the unchanged medium tier (`docs/results/medium-no-plan-diagnosis-2026-10-30.md`). (b) Large tier 60/60/18/18/12/12 s piloted on seeds 101 to 103 plus the two seed-1 failures (both now solve); chosen, in `SolverSettings.for_problem`, spec section 5, ADR 0006; 135 large scenarios frozen, so `scenarios/frozen/` holds all 405 (`docs/results/large-tier-pilot-2026-10-30.csv`). (c) Baselines re-solve from scratch and sequential per-domain repair (spec section 9) are in `Method` and the CLI. (d) Eval harness, stats and report (`eval/`), `smartcampus eval` and `compare` work (spec section 10). 989 tests pass (about 8.5 min); ruff and mypy clean. Merged feature branches still exist; do not delete them. Gate 2 code is in; the evidence run is not.

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
- Hint: `solve()` completes the start-plan hint by solving a copy of the model with the hinted variables fixed (`fix_variables_to_their_hinted_value`, limit 10 s, outside the stage budget) and hints every variable; after each stage the hint is the full solution. `repair_hint` was tried and is worse. ADR 0006.
- Re-solve: stages P, D, S skipped (`SolverSettings.skip_stages`), their seconds split equally between C and K, no hint. Sequential: three restricted solves (`solve(..., restrict=)` fixes or forbids decision variables only, no rule logic): rooms (original start, no equipment moves), equipment (retry the cancelled at original start, moves allowed), timing (retry the still-cancelled with free start). Deviation from the first sketch: pass 1 does not relax R4 (that would need rule logic outside `rules/`); a class needing equipment its rooms lack is cancelled in pass 1 and rescued in pass 2. Approved by the user as "go with your recommendations".
- Eval: `RunResult.planning_seconds` and `start_plan_seconds` give joint's greedy time separately. A method with no plan is a `NO_PLAN` record; sensitivity scores it as the cancel-everything plan and a loss. Six metrics tested separately, no multiplicity correction (stated in the report's threats).
- scipy has no stubs: a mypy override ignores missing imports for `scipy.*`.

## Blockers / open questions
- Spec assumptions 1 to 24 are confirmed by the user (2026-10-30). The frozen v1.0 evaluation set is 405 instances in `scenarios/frozen/` (20 smoke instances are separate and not counted).
- The full run (about 24 to 36 hours, estimate) is deferred to the end (ADR 0007), when all five methods exist; run it in the background with `uv run smartcampus eval scenarios/frozen/ --methods all --out results/ > var/eval.log 2>&1` and Monitor `var/eval.log`. It resumes from `results/results.jsonl`.
- Plan rate per size is unknown until that run; report remaining no-plans as a solver limit. `large-l90-room-s102` (pilot seed) ended with 1 cancellation on both tiers with every stage at its time limit.
- Decisions for `impact/`: window = plan time (or first affected day start) to the end of the last affected day; affected = overlap a fault or hold; movable = affected plus not-yet-started classes in the window within 10 minutes' walk; faults and holds are clipped to plan time. Approval triggers (spec section 6) are not built: `run` applies the plan directly.

## Next step
Decision (ADR 0007): implement everything first, run the full evaluation once at the end. Order: repair-overrun loop and approval triggers; contract-net (short spec section first, show the user); stamp eval records with commit, settings and generator version; one-seed-per-cell check (27 instances); optional results page; freeze, then the full run. ITC 2019 loader only if the user has the data files. Possible: greedy and resolve times on large; speed up R2/R1 `check`. Push and PR only with approval; watch CI with Monitor (include the secrets job).
