# System Patterns

## Naming conventions
- Package `smartcampus` under `src/`. Modules and functions use snake_case, classes PascalCase.
- Test files: `tests/unit/test_<module>.py`, `tests/property/test_<rule>_props.py`, `tests/golden/test_<scenario>.py`.

## Folder structure logic
- One subpackage per responsibility, as in `architecture.md`. Each has a docstring in its `__init__.py` saying what it owns.
- Hard rules only in `rules/`. State changes only through the event log in `sim/`.

## Common patterns used in this project
- CLI commands live in `cli.py` as a Typer app. Unfinished commands call `_not_implemented()`, which exits with code 1 so stubs fail loudly instead of looking like they worked.
- Type hints everywhere. `rules/`, `solver/` and `sim/` are checked with strict mypy flags.
- Dependencies are managed with uv. `uv.lock` is committed because CI runs `uv sync --frozen`.

## Things to avoid
- Duplicating a hard rule outside `rules/`.
- Editing `scenarios/frozen/`.
- Hardcoding secrets. Config comes from `.env`, and `.env.example` lists names only.
- Writing files with a BOM or CRLF line endings (PowerShell `Set-Content -Encoding utf8` adds a BOM; ruff panics on it).
