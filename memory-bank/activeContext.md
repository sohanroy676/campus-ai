# Active Context

<!-- Update this at the end of every session. This is the first thing to read when resuming. -->

## Current focus
Branch `feature/freeze-prep` (from `main` 0501b34, CI on main green: `checks` and `secrets` seen). The pre-freeze decisions 1 to 9 are implemented (see progress.md); the code is ready to freeze once the user says so. Not done, by design: tag, dry run on `scenarios/smoke/` (item 10), the full 405 run. Do not push or open a PR without approval.

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

## Recovery loop (feature/recovery-loop)
- Built: approval triggers, re-plan base, `recover`, CLI `cascade`; ADR 0008. Approval lives on `PlanApplied.approval`. `run` and eval unchanged. Round 1 of `recover` uses the scenario's own window and movable set; later rounds derive them. Known gap: equipment lent to a class that already started is taken as delivered, not as still on loan.

## Contract-net (feature/recovery-loop)
- Built and in spec section 9. Time limit = the tier's total solver seconds, wall clock; on medium and large the initial auction (as slow as greedy, 90 s or more) may use most of it, so those results can be limit-bound: check on the ~20-instance subset before the full run. Agents hold no rule logic: a room agent bids for rooms of the wrong type too and the validator refuses them (same cost as greedy).

- Contract-net subset check done (see progress.md): no large or medium no-plans, 5 of 14 runs limit-bound. The one-seed-per-cell check (27 instances, about 2 hours, greedy and joint at least) is the remaining cheap check.

## Demo dashboard (2026-10-31)
- `smartcampus demo` serves the live dashboard (ADR 0011, `docs/demo.md`). It only reads the frozen code paths (`plan_with_method`, `replan_problem`, `assess`, validator); no rule logic in `api/`. fastapi and uvicorn are in the dev group too, so CI covers `api/`.

## Next step
User says the code is frozen -> tag the commit -> dry run on `scenarios/smoke/` (all methods, report.md, check by eye, kill and resume once, delete the results) -> full run per ADR 0007 (clean tree, empty `results/`, sleep disabled, memory log, one job at a time). Estimate about 20 h, up to 30 h. Optional before: results page, ITC 2019 loader (only with data files), `approve`/`reject` command.

## Large check (2026-10-31)
- One seed per cell on large done (`docs/results/large-check-2026-10-31.md`): no joint or greedy no-plan. Two open issues before the freeze: (1) contract-net's cap (tier total) is shorter than greedy's own first auction on `large-l90-building-s2` (192 s against 180 s), so it ends worse than greedy; (2) resolve returns cancel-everything or heavy-cancel plans on large with status `plan`. Both await the user's decision. Joint takes up to 402 s on large, so the 24 to 36 hour estimate is probably low.
