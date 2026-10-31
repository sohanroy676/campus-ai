"""The live demo session: incidents go into the log, proposals do not, apply does."""

import pytest

from smartcampus.api.demo import DEMO_METHODS, DemoError, DemoSession
from smartcampus.coordinator.run import Method
from smartcampus.domain.events import FaultOccurred, PlanApplied, RepairOverrun
from smartcampus.rules.validator import validate

TUE_08 = 1920
TUE_10 = 2040
TUE_14 = 2280


@pytest.fixture
def session() -> DemoSession:
    s = DemoSession("ac-failure")
    yield s
    s.close()


def inject(s: DemoSession) -> None:
    s.report_fault("AI-Lab-01", "ac_failure", TUE_10, TUE_14)


def test_normal_campus_has_no_incident_and_nothing_to_plan(session: DemoSession) -> None:
    snap = session.snapshot()
    assert snap["faults"] == [] and snap["impact"] is None and snap["events"] == []
    assert snap["clock"] == {"min": TUE_08, "label": "Tue 08:00"}
    assert {r["id"] for r in snap["rooms"]} == {"AI-Lab-01", "AI-Lab-02", "Lec-A1", "Lec-B1"}
    assert all(c["status"] == "unchanged" for c in snap["timetable"])
    assert snap["suggested_incident"] == {
        "room_id": "AI-Lab-01",
        "kind": "ac_failure",
        "start": TUE_10,
        "end": TUE_14,
    }
    with pytest.raises(DemoError, match="report an incident first"):
        session.propose(Method.JOINT)


def test_unknown_scenario_is_refused() -> None:
    with pytest.raises(DemoError, match="unknown scenario"):
        DemoSession("no-such-campus")


def test_incident_is_logged_and_analysed_by_the_agents(session: DemoSession) -> None:
    steps = session.report_fault("AI-Lab-01", "ac_failure", TUE_10, TUE_14)
    agents = [s.agent for s in steps]
    assert agents[:2] == ["Maintenance agent", "Impact analysis"]
    assert "Room agents" in agents and "Equipment agent" in agents
    [event] = session._store.events()
    assert isinstance(event, FaultOccurred) and event.at_min == TUE_08
    snap = session.snapshot()
    assert snap["impact"]["affected"] == ["ml-lab"]
    assert next(c for c in snap["timetable"] if c["id"] == "ml-lab")["affected"]
    assert snap["rooms"][0]["faults"][0]["label"] == "Tue 10:00 to 14:00"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("Nope", "ac_failure", TUE_10, TUE_14), "unknown room"),
        (("AI-Lab-01", "meteor", TUE_10, TUE_14), "unknown fault kind"),
        (("AI-Lab-01", "ac_failure", TUE_14, TUE_10), "bad fault interval"),
        (("AI-Lab-01", "ac_failure", TUE_08 - 120, TUE_08), "already over"),
        (("AI-Lab-01", "ac_failure", TUE_10, TUE_14, TUE_08 - 30), "clock is at"),
    ],
)
def test_bad_incidents_are_refused_and_leave_the_log_empty(
    session: DemoSession, args: tuple, message: str
) -> None:
    with pytest.raises(DemoError, match=message):
        session.report_fault(*args)
    assert session._store.version == 0


def test_every_method_proposes_a_valid_plan_without_writing_state(session: DemoSession) -> None:
    inject(session)
    for method in DEMO_METHODS:
        steps = session.propose(method)
        assert any(s.agent == "Rule validator" for s in steps)
    assert session._store.version == 1  # proposals are not events
    problem = session.current_problem()
    assert problem is not None
    for proposal in session.proposals.values():
        assert proposal.plan is not None and validate(problem, proposal.plan) == []
    snap = session.snapshot()
    # The golden demo result: joint moves 26 people, greedy 55.
    assert snap["proposals"]["joint"]["values"]["people_moved"] == 26
    assert snap["proposals"]["greedy"]["values"]["people_moved"] == 55
    # Sequential ties with joint here; the tie goes to joint.
    assert snap["recommended"] == "joint"
    joint_steps = [s for s in session.steps if s.agent == "Optimizer (CP-SAT)"]
    assert len(joint_steps) == 6  # one per lexicographic stage


def test_apply_appends_the_plan_and_updates_the_timetable(session: DemoSession) -> None:
    inject(session)
    session.propose(Method.GREEDY)
    session.propose(Method.JOINT)
    steps = session.apply(Method.JOINT)
    assert "1 class(es) moved" in steps[-1].text
    events = session._store.events()
    assert isinstance(events[-1], PlanApplied)
    assert events[-1].approval is not None and events[-1].approval.approver == "not_needed"
    snap = session.snapshot()
    ml = next(c for c in snap["timetable"] if c["id"] == "ml-lab")
    assert (ml["room"], ml["status"], ml["original_room"]) == ("AI-Lab-02", "moved", "AI-Lab-01")
    assert snap["proposals"] == {} and snap["recommended"] is None
    assert snap["last_round"]["applied"] == "joint"
    assert set(snap["last_round"]["proposals"]) == {"greedy", "joint"}
    assert snap["applied"][0]["moved"] == 1
    assert snap["loans"][0]["pool"] == "gpu-01" and snap["loans"][0]["to_room"] == "AI-Lab-02"
    assert snap["impact"]["affected"] == []


def test_apply_needs_a_current_proposal(session: DemoSession) -> None:
    inject(session)
    with pytest.raises(DemoError, match="no current proposal"):
        session.apply(Method.JOINT)
    session.propose(Method.GREEDY)
    session.report_fault("Lec-B1", "power_outage", TUE_14, TUE_14 + 60)  # makes it stale
    with pytest.raises(DemoError, match="no current proposal"):
        session.apply(Method.GREEDY)
    assert not any(isinstance(e, PlanApplied) for e in session._store.events())


def test_overrun_after_a_plan_replans_from_the_applied_state() -> None:
    s = DemoSession("ac-cascade")
    try:
        inc = s.suggested_incident()
        s.report_fault(inc["room_id"], inc["kind"], inc["start"], inc["end"])
        s.propose(Method.JOINT)
        s.apply(Method.JOINT)
        fault_id = s.snapshot()["faults"][0]["id"]
        with pytest.raises(DemoError):  # an overrun must end later than the fault does
            s.report_overrun(fault_id, inc["end"], 2160)
        steps = s.report_overrun(fault_id, 2400, 2160)
        assert steps[0].agent == "Maintenance agent"
        assert isinstance(s._store.events()[-1], RepairOverrun)
        assert s.clock == 2160 and s.snapshot()["last_round"] is None
        s.propose(Method.JOINT)
        s.apply(Method.JOINT)
        assert s._store.version == 4
        with pytest.raises(DemoError, match="clock is at"):
            s.report_overrun(fault_id, 2460, 2100)
    finally:
        s.close()


def test_triggered_plan_is_applied_with_the_officer_as_approver() -> None:
    s = DemoSession("generated-small")
    try:
        inc = s.suggested_incident()
        s.report_fault(inc["room_id"], inc["kind"], inc["start"], inc["end"])
        s.propose(Method.GREEDY)
        triggers = s.snapshot()["proposals"]["greedy"]["triggers"]
        assert triggers  # greedy moves over 100 people across buildings here
        s.apply(Method.GREEDY)
        last = s._store.events()[-1]
        assert isinstance(last, PlanApplied) and last.approval is not None
        assert last.approval.approver == "officer"
        assert list(last.approval.triggers) == triggers
    finally:
        s.close()


def test_reset_starts_a_fresh_log(session: DemoSession) -> None:
    inject(session)
    session.reset("ac-failure")
    snap = session.snapshot()
    assert snap["version"] == 0 and snap["faults"] == [] and len(snap["steps"]) == 1
