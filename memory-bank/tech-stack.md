# Tech stack

## Languages and core libraries
| Area | Choice | Version |
| --- | --- | --- |
| Language | Python | 3.12 |
| Env and packaging | uv | latest 0.x |
| Optimization | OR-Tools (CP-SAT) | >=9.12,<10 |
| Schemas and validation | Pydantic | >=2.8,<3 |
| CLI | Typer | >=0.12 |
| Storage | SQLite (stdlib sqlite3) + JSON scenario files | bundled with Python |
| Statistics | SciPy (Wilcoxon), NumPy, pandas | SciPy >=1.13, NumPy >=2.0, pandas >=2.2 |
| Plots for the report | Matplotlib | >=3.9 |
| API (from v0.5 only) | FastAPI + Uvicorn | FastAPI >=0.115, Uvicorn >=0.30 |
| Results view (from v0.5 only) | React + Vite + TypeScript | React 18.3, Vite 5, TS 5 |
| Optional LLM (stretch, off by default) | OpenAI Python SDK | >=1.40 |

## Testing
- Framework: pytest >=8, Hypothesis >=6 (property tests), pytest-cov.
- Location and naming: `tests/unit/test_<module>.py`, `tests/property/test_<rule>_props.py`, `tests/golden/test_<scenario>.py`. Golden scenario inputs and expected outputs live in `tests/golden/data/`.
- Run all: `uv run pytest`
- Fast unit only: `uv run pytest tests/unit -q`
- With coverage: `uv run pytest --cov=smartcampus --cov-report=term-missing`
- Coverage target: 85% for `rules/`, `solver/`, `sim/`.

## Lint, format, types
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .` (check only: `uv run ruff format --check .`)
- Types: `uv run mypy src` (strict for `rules/`, `solver/`, `sim/`)
- Pre-commit: `uv run pre-commit run --all-files` (ruff, ruff-format, mypy)

## Build, run, dev
- Install: `uv sync`
- Generate a scenario: `uv run smartcampus generate --size small --load 75 --severity room --seed 1 --out scenarios/`
- Run one scenario: `uv run smartcampus run scenarios/small-75-room-s1.json --method joint --report out/run.json`
- Compare methods on one scenario: `uv run smartcampus compare scenarios/small-75-room-s1.json`
- Evaluate a frozen set: `uv run smartcampus eval scenarios/frozen/ --methods all --out results/`
- Live demo dashboard: `uv sync --extra api` then `uv run smartcampus demo [--scenario ac-failure|ac-cascade|generated-small] [--port 8000]` (`docs/demo.md`)
- API (v0.5+): `uv run uvicorn smartcampus.api.app:app --reload --port 8000`
- Web view (v0.5+): `cd web && npm install && npm run dev`

## Solver settings (defaults)
- Time limit per re-plan: 30 s. Evaluation and demo: `num_workers=1`, `random_seed=42`.

## Database and external services
- SQLite file at `var/campus.db` holds the event log and runs. Scenarios are JSON under `scenarios/`.
- ITC 2019 instances (public, downloaded once into `data/itc2019/`, gitignored).
- OpenAI API only if `LLM_ENABLED=true`. The key is read from `.env` and never hardcoded.