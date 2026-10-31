"""Scripted later events (a repair overrun, a second fault) for a cascade run.

A follow-up file is a JSON list of events in the log's own format, without `version` (the log
numbers them): `{"type": "repair_overrun", "at_min": 2160, "fault_id": "...", "new_end_min": 2400}`.
"""

import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from smartcampus.domain.events import Event, FaultOccurred, RepairOverrun, SafetyHoldPlaced

MAX_FOLLOWUP_BYTES = 1_000_000
_EVENT = TypeAdapter[Event](Event)
_ALLOWED = (FaultOccurred, RepairOverrun, SafetyHoldPlaced)


class FollowupError(Exception):
    """The follow-up file cannot be read or holds something that is not a disruption event."""


def load_followups(path: Path) -> list[Event]:
    try:
        if path.stat().st_size > MAX_FOLLOWUP_BYTES:
            raise FollowupError(f"{path}: file is over {MAX_FOLLOWUP_BYTES} bytes")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise FollowupError(f"{path}: cannot read file ({error.strerror or error})") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FollowupError(f"{path}: not valid JSON text ({error})") from error
    if not isinstance(raw, list):
        raise FollowupError(f"{path}: expected a JSON list of events")
    events: list[Event] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise FollowupError(f"{path}: item {index} is not an object")
        try:
            event = _EVENT.validate_python({**item, "version": 0})
        except ValidationError as error:
            raise FollowupError(f"{path}: item {index}: {error.errors()[0]['msg']}") from error
        if not isinstance(event, _ALLOWED):
            raise FollowupError(f"{path}: item {index}: only disruption events are allowed")
        events.append(event)
    return events
