import sqlite3
from pathlib import Path

import pytest
from builders import at, make_plan

from smartcampus.domain.entities import Fault
from smartcampus.domain.events import FaultOccurred, PlanApplied, RepairOverrun
from smartcampus.domain.time import Interval
from smartcampus.sim.state import InvalidEventError, StalePlanError, VersionConflictError, project
from smartcampus.sim.store import CorruptLogError, EventStore

SCHEMA = (
    "CREATE TABLE events (version INTEGER PRIMARY KEY, at_min INTEGER NOT NULL,"
    " type TEXT NOT NULL, payload TEXT NOT NULL);"
)


def occurred(version: int, fault_id: str = "f1", at_min: int = at(1, 8)) -> FaultOccurred:
    interval = Interval(start=at(1, 8), end=at(1, 12))
    fault = Fault(id=fault_id, room_id="A1", kind="ac", interval=interval)
    return FaultOccurred(version=version, at_min=at_min, fault=fault)


def overrun(version: int) -> RepairOverrun:
    return RepairOverrun(version=version, at_min=at(1, 9), fault_id="f1", new_end_min=at(1, 15))


def test_a_new_store_is_empty() -> None:
    with EventStore() as store:
        assert (store.version, store.events()) == (0, [])


def test_appended_events_come_back_in_order() -> None:
    with EventStore() as store:
        store.append(occurred(0))
        store.append(overrun(1))
        assert store.events() == [occurred(0), overrun(1)]
        assert store.version == 2


def test_the_state_equals_a_replay_of_the_log() -> None:
    with EventStore() as store:
        store.append(occurred(0))
        store.append(overrun(1))
        assert store.state == project(store.events())


def test_a_file_store_survives_reopening(tmp_path: Path) -> None:
    path = tmp_path / "var" / "campus.db"  # the parent folder does not exist yet
    with EventStore(path) as store:
        store.append(occurred(0))
        store.append(overrun(1))
        before = store.state
    with EventStore(path) as reopened:
        assert reopened.state == before
        assert reopened.append(occurred(2, "f2", at(1, 10))).version == 3


@pytest.mark.parametrize("version", [1, 5])
def test_a_wrong_version_is_refused_and_nothing_is_written(version: int) -> None:
    with EventStore() as store:
        with pytest.raises(VersionConflictError):
            store.append(occurred(version))
        assert (store.version, store.events()) == (0, [])


def test_a_stale_plan_is_rejected_and_the_log_is_unchanged() -> None:
    with EventStore() as store:
        store.append(occurred(0))
        store.append(overrun(1))
        stale = make_plan().model_copy(update={"based_on_version": 1})
        with pytest.raises(StalePlanError):
            store.append(PlanApplied(version=2, at_min=at(1, 9), plan=stale))
        assert store.version == 2 and len(store.events()) == 2


def test_an_invalid_event_is_not_written() -> None:
    with EventStore() as store:
        with pytest.raises(InvalidEventError):
            store.append(overrun(0))  # no such fault yet
        assert store.events() == []


def test_a_second_writer_taking_the_same_version_is_a_conflict(tmp_path: Path) -> None:
    path = tmp_path / "campus.db"
    with EventStore(path) as first, EventStore(path) as second:
        first.append(occurred(0))
        with pytest.raises(VersionConflictError):
            second.append(occurred(0, "f2"))  # second's cached state is still version 0
        assert first.events() == [occurred(0)]


def test_rows_cannot_be_changed_or_deleted(tmp_path: Path) -> None:
    path = tmp_path / "campus.db"
    with EventStore(path) as store:
        store.append(occurred(0))
    raw = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            raw.execute("UPDATE events SET at_min = 0")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            raw.execute("DELETE FROM events")
    finally:
        raw.close()


def test_a_gap_in_the_stored_versions_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "campus.db"
    event = occurred(1)  # version 1 stored first: the log has a gap
    raw = sqlite3.connect(path)
    raw.executescript(SCHEMA)
    raw.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?)",
        (event.version, event.at_min, event.type, event.model_dump_json()),
    )
    raw.commit()
    raw.close()
    with pytest.raises(CorruptLogError):
        EventStore(path)


def test_garbage_in_the_payload_is_an_error_not_a_silent_skip(tmp_path: Path) -> None:
    path = tmp_path / "campus.db"
    with EventStore(path) as store:
        store.append(occurred(0))
    raw = sqlite3.connect(path)
    raw.execute("DROP TRIGGER events_no_update")
    raw.execute('UPDATE events SET payload = \'{"type": "nonsense"}\'')
    raw.commit()
    raw.close()
    with pytest.raises(ValueError):  # pydantic's ValidationError is a ValueError
        EventStore(path)


def test_ids_with_sql_in_them_are_stored_as_plain_text() -> None:
    nasty = "x'); DROP TABLE events;--"
    with EventStore() as store:
        store.append(occurred(0, nasty))
        [stored] = store.events()
        assert isinstance(stored, FaultOccurred)
        assert stored.fault.id == nasty
