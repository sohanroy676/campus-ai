"""Replaying a log always rebuilds the state it produced, and bad events never reach the log."""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.events import (
    Event,
    FaultOccurred,
    PlanApplied,
    RepairOverrun,
    SafetyHoldPlaced,
)
from smartcampus.domain.plan import Plan
from smartcampus.domain.time import Interval
from smartcampus.sim.state import InvalidEventError, SimState, apply_event, project
from smartcampus.sim.store import EventStore


@st.composite
def valid_logs(draw: st.DrawFn) -> list[Event]:
    """A log built by always drawing an event that the current state accepts."""
    state = SimState()
    log: list[Event] = []
    for n in range(draw(st.integers(0, 12))):
        at_min = state.now_min + draw(st.integers(0, 60))
        kind = draw(st.sampled_from(["fault", "overrun", "hold", "plan"]))
        start = draw(st.integers(0, 3000))
        interval = Interval(start=start, end=start + draw(st.integers(1, 240)))
        room = draw(st.sampled_from(["A1", "A2"]))
        event: Event
        if kind == "overrun" and state.faults:
            target = draw(st.sampled_from(state.faults))
            event = RepairOverrun(
                version=n,
                at_min=at_min,
                fault_id=target.id,
                new_end_min=target.interval.end + draw(st.integers(1, 240)),
            )
        elif kind == "hold":
            hold = SafetyHold(target_kind="room", target_id=room, interval=interval)
            event = SafetyHoldPlaced(version=n, at_min=at_min, hold=hold)
        elif kind == "plan":
            event = PlanApplied(version=n, at_min=at_min, plan=Plan(based_on_version=n))
        else:
            fault = Fault(id=f"f{n}", room_id=room, kind="ac", interval=interval)
            event = FaultOccurred(version=n, at_min=at_min, fault=fault)
        state = apply_event(state, event)
        log.append(event)
    return log


@settings(max_examples=60)
@given(valid_logs())
def test_the_store_state_always_equals_a_replay(log: list[Event]) -> None:
    with EventStore() as store:
        for event in log:
            store.append(event)
        assert store.events() == log
        assert store.state == project(log)
        assert store.version == len(log)


@settings(max_examples=30)
@given(valid_logs())
def test_reopening_a_file_store_gives_the_same_state(log: list[Event]) -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "campus.db"
        with EventStore(path) as store:
            for event in log:
                store.append(event)
            before = store.state
        with EventStore(path) as reopened:
            assert reopened.state == before
            assert reopened.events() == log


@settings(max_examples=60)
@given(valid_logs(), st.integers(0, 20))
def test_an_event_with_the_wrong_version_never_changes_anything(
    log: list[Event], version: int
) -> None:
    state = project(log)
    if version == state.version:
        version += 1
    wrong = PlanApplied(version=version, at_min=state.now_min, plan=Plan(based_on_version=0))
    with pytest.raises(InvalidEventError):
        apply_event(state, wrong)
    assert project(log) == state


@settings(max_examples=60)
@given(valid_logs(), st.integers(0, 30))
def test_a_plan_is_accepted_only_on_the_current_version(log: list[Event], based_on: int) -> None:
    state = project(log)
    plan = Plan(based_on_version=based_on)
    event = PlanApplied(version=state.version, at_min=state.now_min, plan=plan)
    if based_on == state.version:
        assert apply_event(state, event).version == state.version + 1
    else:
        with pytest.raises(InvalidEventError):
            apply_event(state, event)
