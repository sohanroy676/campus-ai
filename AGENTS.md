# AGENTS.md
Simulated campus that re-plans rooms, equipment and timing after disruptions using one CP-SAT model; evaluated against baselines on generated scenarios.

Stack: Python 3.12, uv, OR-Tools CP-SAT, Pydantic 2, Typer, SQLite/JSON, pytest + Hypothesis, ruff, mypy.

Commands: `uv sync` · `uv run pytest` · `uv run ruff check . && uv run ruff format --check .` · `uv run mypy src` · `uv run smartcampus run <scenario.json> --method joint`

- Hard rules live only in `src/smartcampus/rules/`; the solver and validator both import them. Never duplicate a rule.
- State changes only by appending events in `sim/`; agents and baselines never write state.
- Evaluation and golden tests use `num_workers=1`, `random_seed=42`; never edit files in `scenarios/frozen/`.
- Secrets only in `.env`; the system must run with `LLM_ENABLED=false`.

Detailed rules: see `.claude/rules/` (and CLAUDE.md).