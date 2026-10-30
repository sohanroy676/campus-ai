# CLAUDE.md

@AGENTS.md

## Session context
@memory-bank/projectBrief.md
@memory-bank/activeContext.md
@memory-bank/progress.md

Read on demand: `memory-bank/architecture.md` (module layout, incident flow), `memory-bank/tech-stack.md` (commands, test locations, solver settings), `memory-bank/systemPatterns.md`, `ROADMAP.md`, `docs/adr/` (decision records).

## Status
Gate 1 is reached: `src/smartcampus/` has the rules, solver, sim, impact, generator, greedy baseline and CLI `run`/`generate`, with tests. Build order follows `ROADMAP.md`. Modules in `architecture.md` that are not built yet (sequential and re-solve baselines, eval, contract-net, API) may not exist; check first.

## Commands
- Install: `uv sync`
- Tests: `uv run pytest` (fast: `uv run pytest tests/unit -q`; coverage: `uv run pytest --cov=smartcampus --cov-report=term-missing`)
- Lint/format/types: `uv run ruff check .` · `uv run ruff format .` · `uv run mypy src`
- Run a scenario: `uv run smartcampus run <scenario.json> --method joint`
- Full command list: `memory-bank/tech-stack.md`

## Hard design rules (do not violate)
- Hard rules live only in `src/smartcampus/rules/`; solver and validator both import them. Never duplicate a rule.
- State changes only by appending events in `sim/`; agents and baselines never write state.
- Evaluation and golden tests use `num_workers=1`, `random_seed=42`. Never edit `scenarios/frozen/`.
- Secrets only in `.env`; the system must run with `LLM_ENABLED=false`. The LLM never checks rules, picks plans or writes state.

## Workflow
Rules live in `.claude/rules/` (security, testing, commit style, self-review, git workflow, session efficiency) and are loaded automatically. Slash commands: `/new-feature`, `/debug`, `/commit` (in `.claude/commands/`). Work on feature branches, never commit to `main`, never push without approval. At the end of a session update `memory-bank/progress.md` and `activeContext.md`.

## Background tasks: use Monitor
Never poll or sleep-and-check background work (dev servers, long solver/eval runs, CI, test watchers).
- One completion event ("tell me when the eval finishes", "when the server is ready"): `Bash` with `run_in_background`, using a command that exits when done.
- A stream of events (every failure, every CI check, solver/eval progress): the `Monitor` tool with a line-buffered filter.
- Filters must cover failure as well as success, e.g. `grep -E --line-buffered "Traceback|Error|FAILED|INFEASIBLE|Killed|passed|done"`. Silence is not success.
- Long evals: `uv run smartcampus eval scenarios/frozen/ --methods all --out results/ > var/eval.log 2>&1` in the background, then Monitor `var/eval.log`.
- CI after a push: Monitor `gh run watch` / `gh pr checks` (poll >= 30s) and emit every terminal state (success, failure, cancelled). Do not report CI green without having seen it.
- Give each monitor a specific `description`; stop finished ones with `TaskStop`.
