"""Scenario files: a `RecoveryProblem` serialized as JSON.

A file either states `window` and `movable_activity_ids` or leaves out both, in which case
`impact/` derives them (and clips the faults and holds to plan time) from the disruptions.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from smartcampus.domain.problem import RecoveryProblem
from smartcampus.impact.derive import derive_recovery

MAX_SCENARIO_BYTES = 5_000_000  # a hand-made or generated scenario is far smaller

_DERIVED_KEYS = frozenset({"window", "movable_activity_ids"})
_DRAFT_FIELDS: dict[str, Any] = {"window": {"start": 0, "end": 1}, "movable_activity_ids": []}

# Set-valued fields are written sorted, so the same problem always gives the same file.
_SET_FIELDS = frozenset({"allowed_room_types", "movable_activity_ids"})


class ScenarioError(Exception):
    """The scenario file cannot be read or does not describe a valid problem."""


def load_scenario(path: Path) -> RecoveryProblem:
    try:
        size = path.stat().st_size
        if size > MAX_SCENARIO_BYTES:
            raise ScenarioError(
                f"{path}: file is {size} bytes, over the {MAX_SCENARIO_BYTES} limit"
            )
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ScenarioError(f"{path}: cannot read file ({error.strerror or error})") from error
    except UnicodeDecodeError as error:
        raise ScenarioError(f"{path}: not UTF-8 text") from error
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        raw = None  # the validation error below describes it
    derive = isinstance(raw, dict) and _DERIVED_KEYS.isdisjoint(raw)
    if isinstance(raw, dict) and not derive and not raw.keys() >= _DERIVED_KEYS:
        raise ScenarioError(
            f"{path}: give both window and movable_activity_ids, or neither "
            "(then they are derived from the faults and holds)"
        )
    try:
        if derive:
            return derive_recovery(RecoveryProblem.model_validate({**raw, **_DRAFT_FIELDS}))
        return RecoveryProblem.model_validate_json(text)
    except ValidationError as error:
        raise ScenarioError(f"{path}: not a valid scenario\n{_summary(error)}") from error


def dump_scenario(problem: RecoveryProblem) -> str:
    """Canonical JSON text: two-space indent, sorted set fields, LF, trailing newline."""
    data = _sort_sets(problem.model_dump(mode="json", exclude_none=True))
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def save_scenario(problem: RecoveryProblem, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_scenario(problem), encoding="utf-8", newline="\n")


def _sort_sets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sorted(item) if key in _SET_FIELDS else _sort_sets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sort_sets(item) for item in value]
    return value


def _summary(error: ValidationError, limit: int = 5) -> str:
    """The first few problems, each with the path to the bad field."""
    lines = [
        f"  {'.'.join(str(part) for part in problem['loc']) or '<file>'}: {problem['msg']}"
        for problem in error.errors()[:limit]
    ]
    if error.error_count() > limit:
        lines.append(f"  ... and {error.error_count() - limit} more")
    return "\n".join(lines)
