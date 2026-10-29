import sqlite3
from pathlib import Path

import pytest
from builders import at

from smartcampus.domain.entities import Fault
from smartcampus.domain.events import FaultOccurred
from smartcampus.domain.time import Interval
from smartcampus.sim.store import EventStore


def occurred(version: int = 0) -> FaultOccurred:
    interval = Interval(start=at(1, 8), end=at(1, 12))
    fault = Fault(id="f1", room_id="A1", kind="ac", interval=interval)
    return FaultOccurred(version=version, at_min=at(1, 8), fault=fault)


def test_a_missing_path_gets_a_new_empty_log(tmp_path: Path) -> None:
    with EventStore.create_fresh(tmp_path / "var" / "campus.db") as store:
        assert (store.version, store.events()) == (0, [])


def test_an_earlier_event_log_is_replaced(tmp_path: Path) -> None:
    path = tmp_path / "campus.db"
    with EventStore(path) as old:
        old.append(occurred())
    with EventStore.create_fresh(path) as fresh:
        assert (fresh.version, fresh.events()) == (0, [])
        fresh.append(occurred())  # version 0 is free again


def test_a_relative_path_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for _ in range(2):  # the second round replaces the log written by the first
        with EventStore.create_fresh(Path("var") / "campus.db") as store:
            store.append(occurred())
    assert (tmp_path / "var" / "campus.db").is_file()


def test_an_empty_file_is_replaced(tmp_path: Path) -> None:
    path = tmp_path / "campus.db"
    path.touch()
    with EventStore.create_fresh(path) as store:
        assert store.version == 0


def test_a_file_that_is_not_an_event_store_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "thesis.txt"
    path.write_text("my only copy", encoding="utf-8")
    with pytest.raises(ValueError, match="not an event store"):
        EventStore.create_fresh(path)
    assert path.read_text(encoding="utf-8") == "my only copy"


def test_another_sqlite_database_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "other.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE notes (body TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="not an event store"):
        EventStore.create_fresh(path)
    assert path.exists()


def test_a_directory_is_left_alone(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not an event store"):
        EventStore.create_fresh(tmp_path)
    assert tmp_path.is_dir()
