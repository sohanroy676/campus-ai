"""Append-only event store in SQLite. This is the only way simulation state changes.

Rows are never updated or deleted (triggers enforce it). An event is checked against the current
state before it is written, so an invalid event never reaches the log.
"""

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self

from pydantic import TypeAdapter

from smartcampus.domain.events import Event
from smartcampus.sim.state import SimState, VersionConflictError, apply_event

_EVENT: TypeAdapter[Event] = TypeAdapter(Event)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    version INTEGER PRIMARY KEY,
    at_min  INTEGER NOT NULL,
    type    TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'the event log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'the event log is append-only'); END;
"""


class CorruptLogError(Exception):
    """The stored log is not a dense run of versions 0, 1, 2, ... that replays cleanly."""


class EventStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.executescript(_SCHEMA)
        self._state = SimState()
        try:
            for stored in self.events():
                self._state = apply_event(self._state, stored)
        except Exception:
            self._conn.close()
            raise

    @property
    def state(self) -> SimState:
        return self._state

    @property
    def version(self) -> int:
        return self._state.version

    def events(self) -> list[Event]:
        rows = self._conn.execute("SELECT version, payload FROM events ORDER BY version").fetchall()
        events = [_EVENT.validate_json(payload) for _, payload in rows]
        if [version for version, _ in rows] != list(range(len(rows))):
            raise CorruptLogError("event versions are not 0, 1, 2, ... without gaps")
        return events

    def append(self, event: Event) -> SimState:
        """Write `event` and return the new state; raises `InvalidEventError` if it is refused."""
        new_state = apply_event(self._state, event)
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO events (version, at_min, type, payload) VALUES (?, ?, ?, ?)",
                    (event.version, event.at_min, event.type, event.model_dump_json()),
                )
        except sqlite3.IntegrityError as error:  # another writer took this version
            raise VersionConflictError(f"version {event.version} is already in the log") from error
        self._state = new_state
        return new_state

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
