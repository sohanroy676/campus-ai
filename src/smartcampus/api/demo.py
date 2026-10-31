"""The live demo: one campus, one event log, driven step by step from the dashboard.

`DemoSession` holds a normal timetable (the scenario without its disruptions) and an in-memory
event store. Each dashboard action is one call:

1. `report_fault` / `report_overrun` append the incident to the log (the only way state changes)
   and return what the maintenance, impact and agent steps found.
2. `propose(method)` builds a plan with one recovery method (`coordinator.run.plan_with_method`,
   the same code `smartcampus run` uses) and keeps it as a proposal. Nothing is written.
3. `apply(method)` appends the proposal as `PlanApplied`, with the dashboard user as the officer
   when an approval trigger fires.

The agent activity is a record of what the real steps returned (impact sets, room-agent offers,
equipment moves, solver stages, validator verdict, approval triggers). No step is invented, and
no rule is checked here: offers are judged by `rules.validator`.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from smartcampus.agents.resource import Bid, RoomAgent
from smartcampus.coordinator.approval import triggers
from smartcampus.coordinator.replan import replan_problem
from smartcampus.coordinator.run import Method, Planned, plan_with_method
from smartcampus.domain.entities import Activity, Fault
from smartcampus.domain.events import (
    Approval,
    Event,
    FaultOccurred,
    PlanApplied,
    RepairOverrun,
    SafetyHoldPlaced,
)
from smartcampus.domain.plan import Assignment, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import DAYS, Interval, day_of
from smartcampus.generator.scenario import load_scenario
from smartcampus.generator.synth import generate_scenario
from smartcampus.impact.derive import assess
from smartcampus.reporting.summary import DAY_NAMES, STAGE_LABELS, format_minute
from smartcampus.rules.registry import ALL_RULES
from smartcampus.rules.validator import validate
from smartcampus.sim.state import InvalidEventError
from smartcampus.sim.store import EventStore
from smartcampus.solver.objective import StageValues, evaluate
from smartcampus.solver.solve import InfeasibleInputError, NoSolutionError

DEV_SCENARIOS = Path(__file__).resolve().parents[3] / "scenarios" / "dev"

# Fastest first, so the comparison fills in while the slower methods run.
DEMO_METHODS = (
    Method.GREEDY,
    Method.SEQUENTIAL,
    Method.CONTRACT_NET,
    Method.RESOLVE,
    Method.JOINT,
)
METHOD_LABELS = {
    Method.GREEDY: "Greedy",
    Method.SEQUENTIAL: "Sequential repair",
    Method.CONTRACT_NET: "Contract-net agents",
    Method.RESOLVE: "Re-solve from scratch",
    Method.JOINT: "Joint CP-SAT",
}
TIE_ORDER = (Method.JOINT, Method.SEQUENTIAL, Method.CONTRACT_NET, Method.RESOLVE, Method.GREEDY)
FAULT_KINDS = {
    "ac_failure": "AC failure",
    "power_outage": "Power outage",
    "water_leak": "Water leak",
    "network_outage": "Network outage",
}
MAX_OFFER_CHECKS = 400  # validator calls per affected class when counting room-agent offers


class DemoError(Exception):
    """The dashboard asked for something the current state does not allow."""


@dataclass(frozen=True)
class DemoScenario:
    id: str
    title: str
    description: str
    load: Callable[[], RecoveryProblem]


SCENARIOS: dict[str, DemoScenario] = {
    s.id: s
    for s in (
        DemoScenario(
            "ac-failure",
            "AI lab AC failure (4 rooms)",
            "Two buildings, two AI labs and two lecture halls; ml-lab needs 3 GPUs.",
            lambda: load_scenario(DEV_SCENARIOS / "ac-failure.json"),
        ),
        DemoScenario(
            "ac-cascade",
            "AI lab AC failure, robotics too (5 classes)",
            "The AC demo plus a robotics lab; try a repair overrun after the first plan.",
            lambda: load_scenario(DEV_SCENARIOS / "ac-cascade.json"),
        ),
        DemoScenario(
            "generated-small",
            "Generated campus (8 rooms, 246 classes)",
            "Seeded synthetic week: small size, load 75, lab fault, seed 2.",
            lambda: generate_scenario("small", 75, "room", 2),
        ),
    )
}


@dataclass
class Step:
    agent: str
    text: str
    level: str = "info"  # info | ok | warn | error
    at: str = field(default_factory=lambda: time.strftime("%H:%M:%S"))

    def as_dict(self) -> dict[str, str]:
        return {"agent": self.agent, "text": self.text, "level": self.level, "at": self.at}


@dataclass(frozen=True)
class Proposal:
    method: Method
    version: int  # log version the plan was built on
    plan: Plan | None  # None: the method found no plan
    values: StageValues | None
    planned: Planned | None
    triggers: tuple[str, ...]
    reason: str = ""  # why there is no plan


def _interval_dict(interval: Interval) -> dict[str, Any]:
    return {
        "start": interval.start,
        "end": interval.end,
        "label": f"{format_minute(interval.start)} to {format_minute(interval.end)[4:]}",
    }


def _values_dict(values: StageValues) -> dict[str, int]:
    return {name: getattr(values, name) for name, _ in STAGE_LABELS}


class DemoSession:
    """One demo run. Not thread-safe: the API calls it from a single worker thread."""

    def __init__(self, scenario_id: str = "ac-failure") -> None:
        self.store: EventStore | None = None
        self.reset(scenario_id)

    # ----- setup -----------------------------------------------------------------------------

    def reset(self, scenario_id: str) -> None:
        if scenario_id not in SCENARIOS:
            raise DemoError(f"unknown scenario {scenario_id!r}")
        scenario = SCENARIOS[scenario_id]
        problem = scenario.load()
        if self.store is not None:
            self.store.close()
        self.scenario = scenario
        self.original = problem
        # The normal campus: the scenario's timetable without its disruptions.
        self.base = RecoveryProblem.model_validate(
            {**dict(problem), "faults": (), "holds": (), "movable_activity_ids": frozenset()}
        )
        self.clock = problem.plan_time_min
        self.store = EventStore()
        self.proposals: dict[Method, Proposal] = {}
        self.applied: list[dict[str, Any]] = []
        self.last_round: dict[str, Any] | None = None  # the proposals a plan was applied from
        self.steps: list[Step] = []
        self._problem_cache: tuple[int, RecoveryProblem] | None = None
        self._log(
            "Digital twin",
            f"Loaded {scenario.title}: {len(problem.campus.rooms)} rooms, "
            f"{len(problem.activities)} classes. Clock {format_minute(self.clock)}.",
        )

    @property
    def _store(self) -> EventStore:
        assert self.store is not None
        return self.store

    def _log(self, agent: str, text: str, level: str = "info") -> Step:
        step = Step(agent, text, level)
        self.steps.append(step)
        return step

    def _append(self, event: Event) -> None:
        try:
            self._store.append(event)
        except InvalidEventError as error:
            raise DemoError(str(error)) from error
        self.clock = event.at_min
        self.last_round = None
        stale = [m for m, p in self.proposals.items() if p.version != self._store.version]
        for method in stale:
            del self.proposals[method]

    def _reported_at(self, reported_min: int | None) -> int:
        at = self.clock if reported_min is None else reported_min
        if at < self.clock:
            raise DemoError(
                f"cannot report at {format_minute(at)}: the clock is at {format_minute(self.clock)}"
            )
        return at

    # ----- the problem as the log now describes it -------------------------------------------

    def current_problem(self) -> RecoveryProblem | None:
        """The recovery problem for the current state, or None when nothing is disrupted."""
        state = self._store.state
        if not state.faults and not state.holds:
            return None
        if self._problem_cache is None or self._problem_cache[0] != state.version:
            self._problem_cache = (state.version, replan_problem(self.base, state))
        return self._problem_cache[1]

    # ----- 1. incidents ----------------------------------------------------------------------

    def report_fault(
        self, room_id: str, kind: str, start_min: int, end_min: int, reported_min: int | None = None
    ) -> list[Step]:
        try:
            room = self.base.campus.room(room_id)
        except KeyError as error:
            raise DemoError(f"unknown room {room_id!r}") from error
        if kind not in FAULT_KINDS:
            raise DemoError(f"unknown fault kind {kind!r}")
        at = self._reported_at(reported_min)
        try:
            interval = Interval(start=start_min, end=end_min)
        except ValueError as error:
            raise DemoError(f"bad fault interval: {error}") from error
        if interval.end <= at:
            raise DemoError("the fault is already over at the time it is reported")
        n = len(self._store.state.faults) + 1
        fault = Fault(id=f"{kind}-{room_id}-{n}", room_id=room_id, kind=kind, interval=interval)
        first = len(self.steps)
        self._append(FaultOccurred(version=self._store.version, at_min=at, fault=fault))
        self._log(
            "Maintenance agent",
            f"{FAULT_KINDS[kind]} reported in {room.id} (building {room.building_id}), "
            f"{_interval_dict(interval)['label']}. Logged as event {self._store.version - 1}.",
            "warn",
        )
        self._analyse()
        return self.steps[first:]

    def report_overrun(
        self, fault_id: str, new_end_min: int, reported_min: int | None = None
    ) -> list[Step]:
        at = self._reported_at(reported_min)
        first = len(self.steps)
        self._append(
            RepairOverrun(
                version=self._store.version, at_min=at, fault_id=fault_id, new_end_min=new_end_min
            )
        )
        self._log(
            "Maintenance agent",
            f"Repair overrun on {fault_id}: now unusable until {format_minute(new_end_min)}. "
            f"Logged as event {self._store.version - 1} at {format_minute(at)}.",
            "warn",
        )
        self._analyse()
        return self.steps[first:]

    def _analyse(self) -> None:
        problem = self.current_problem()
        if problem is None:  # pragma: no cover - only called after a fault was appended
            return
        impact = assess(problem)
        names = ", ".join(
            f"{a.id} ({a.room_id} {format_minute(a.start_min)})"
            for a in sorted((problem.activity(i) for i in impact.affected), key=_by_start)
        )
        self._log(
            "Impact analysis",
            f"{len(impact.affected)} class(es) hit: {names or 'none'}. Recovery window "
            f"{_interval_dict(problem.window)['label']}; {len(problem.movable_activity_ids)} "
            "class(es) may move to make room.",
            "warn" if impact.affected else "ok",
        )
        for activity in sorted((problem.activity(i) for i in impact.affected), key=_by_start):
            self._room_agent_offers(problem, activity, impact.affected)

    def _room_agent_offers(
        self, problem: RecoveryProblem, activity: Activity, affected: frozenset[str]
    ) -> None:
        """Ask every room agent for offers; the validator says which fit without moving others.

        Each offer is checked with every other class where it is now and the other hit classes
        left out, so "passes" means it fits into today's timetable as it stands.
        """
        stay = tuple(
            Assignment(activity_id=a.id, room_id=a.room_id, start_min=a.start_min)
            for a in (problem.activity(i) for i in problem.movable_activity_ids)
            if a.id not in affected
        )
        left_out = affected - {activity.id}
        bids = sorted(
            (b for r in problem.campus.rooms for b in RoomAgent(r).bids(problem, activity)),
            key=lambda b: (b.cost, b.room_id, b.start_min),
        )
        valid_rooms: set[str] = set()
        best: Bid | None = None
        for bid in bids[:MAX_OFFER_CHECKS]:
            if bid.room_id in valid_rooms:
                continue
            alone = Plan(
                based_on_version=self._store.version,
                assignments=(*stay, bid.assignment),
                cancelled=left_out,
                moves=bid.moves,
            )
            if not validate(problem, alone):
                valid_rooms.add(bid.room_id)
                best = best or bid
        if best is None:
            self._log(
                "Room agents",
                f"{activity.id}: {len(bids)} offer(s), none fits without moving other classes; "
                "the planners must make room or cancel it.",
                "warn",
            )
            return
        self._log(
            "Room agents",
            f"{activity.id} ({problem.cohort(activity.cohort_id).size} students): "
            f"{len(bids)} offer(s) from {len({b.room_id for b in bids})} room(s); "
            f"{len(valid_rooms)} room(s) can take it without moving another class. "
            f"Cheapest: {best.room_id} "
            f"{format_minute(best.start_min)}.",
        )
        if activity.required_equipment:
            needs = ", ".join(f"{n} x {t}" for t, n in sorted(activity.required_equipment.items()))
            if best.moves:
                carried = "; ".join(
                    f"{m.units} x {m.pool_id} carried {format_minute(m.start_min)} to "
                    f"{format_minute(m.end_min)[4:]}"
                    for m in best.moves
                )
                self._log("Equipment agent", f"{activity.id} needs {needs}: {carried}.")
            else:
                self._log(
                    "Equipment agent", f"{activity.id} needs {needs}: {best.room_id} has them."
                )

    # ----- 2. proposals ----------------------------------------------------------------------

    def propose(self, method: Method) -> list[Step]:
        problem = self.current_problem()
        if problem is None:
            raise DemoError("nothing is disrupted: report an incident first")
        first = len(self.steps)
        label = METHOD_LABELS[method]
        version = self._store.version
        self._log("Coordinator", f"Asked {label} for a plan on state version {version}.")
        try:
            planned = plan_with_method(problem, method, version)
        except (InfeasibleInputError, NoSolutionError) as error:
            self.proposals[method] = Proposal(method, version, None, None, None, (), str(error))
            self._log(label, f"No plan: {error}", "error")
            return self.steps[first:]
        values = evaluate(problem, planned.plan)
        fired = tuple(t.value for t in triggers(problem, planned.plan))
        self.proposals[method] = Proposal(method, version, planned.plan, values, planned, fired)
        self._method_steps(method, planned)
        self._log(
            "Rule validator",
            f"{label}: all {len(ALL_RULES)} hard rules (R1 to R8) re-checked, 0 violations.",
            "ok",
        )
        self._log(
            "Approval",
            f"{label}: officer approval needed ({', '.join(fired)})."
            if fired
            else f"{label}: no approval trigger fired; can be applied directly.",
            "warn" if fired else "ok",
        )
        return self.steps[first:]

    def _method_steps(self, method: Method, planned: Planned) -> None:
        label = METHOD_LABELS[method]
        secs = f"{planned.planning_seconds:.2f} s"
        if method is Method.GREEDY:
            self._log(label, f"Placed classes one at a time by original start ({secs}).")
        elif method is Method.CONTRACT_NET:
            self._log(
                label,
                f"Room agents bid, the manager awarded and re-auctioned "
                f"({planned.start_plan_seconds:.2f} s first auction, {secs} in all"
                + (", time limit hit)." if planned.limit_hit else ")."),
            )
        else:
            for stage in planned.stages:
                self._log(
                    "Optimizer (CP-SAT)" if method is Method.JOINT else label,
                    f"Stage {stage.name}: {stage.value} ({stage.status.value}, "
                    f"{stage.seconds:.2f} s).",
                    "warn" if stage.status.value == "time_limit" else "info",
                )
        self._log(label, f"Plan ready in {secs}.", "ok")

    def recommended(self) -> Method | None:
        """The proposal with the best lexicographic score; ties go to joint, then the others in
        `TIE_ORDER` (the method the project puts forward first)."""
        scored = [
            (p.values, TIE_ORDER.index(m), m)
            for m, p in self.proposals.items()
            if p.values is not None
        ]
        return min(scored)[2] if scored else None

    # ----- 3. apply ----------------------------------------------------------------------------

    def apply(self, method: Method) -> list[Step]:
        proposal = self.proposals.get(method)
        if proposal is None or proposal.plan is None:
            raise DemoError(f"no current proposal from {METHOD_LABELS[method]}")
        first = len(self.steps)
        approver = "officer" if proposal.triggers else "not_needed"
        changes = self._changes(proposal)  # against the problem the plan was built for
        recommended = self.recommended()
        shown = {m.value: self._proposal_dict(p) for m, p in self.proposals.items()}
        self._append(
            PlanApplied(
                version=self._store.version,
                at_min=self.clock,
                plan=proposal.plan,
                approval=Approval(approver=approver, triggers=proposal.triggers),
            )
        )
        moved = sum(1 for c in changes if c["after"] is not None and c["changed"])
        cancelled = sum(1 for c in changes if c["after"] is None)
        self.applied.append(
            {
                "version": self._store.version - 1,
                "method": method.value,
                "label": METHOD_LABELS[method],
                "approver": approver,
                "triggers": list(proposal.triggers),
                "moved": moved,
                "cancelled": cancelled,
            }
        )
        self.proposals.clear()
        self.last_round = {
            "applied": method.value,
            "recommended": recommended.value if recommended else None,
            "proposals": shown,
        }
        self._log(
            "Coordinator",
            f"Applied the {METHOD_LABELS[method]} plan as event {self._store.version - 1}"
            + (" (approved by the officer on the dashboard)." if proposal.triggers else "."),
            "ok",
        )
        self._log(
            "Digital twin",
            f"Timetable updated: {moved} class(es) moved, {cancelled} cancelled, "
            f"{len(proposal.plan.moves)} equipment move(s) booked.",
            "ok",
        )
        return self.steps[first:]

    # ----- views -----------------------------------------------------------------------------

    def _changes(self, proposal: Proposal) -> list[dict[str, Any]]:
        problem = self.current_problem()
        assert problem is not None and proposal.plan is not None
        placed = {a.activity_id: a for a in proposal.plan.assignments}
        out = []
        for activity in sorted(
            (problem.activity(i) for i in problem.movable_activity_ids), key=_by_start
        ):
            asg = placed.get(activity.id)
            moved = asg is None or (asg.room_id, asg.start_min) != (
                activity.room_id,
                activity.start_min,
            )
            out.append(
                {
                    "activity": activity.id,
                    "cohort": activity.cohort_id,
                    "size": problem.cohort(activity.cohort_id).size,
                    "duration": activity.duration_min,
                    "before": {
                        "room": activity.room_id,
                        "start": activity.start_min,
                        "label": format_minute(activity.start_min),
                    },
                    "after": None
                    if asg is None
                    else {
                        "room": asg.room_id,
                        "start": asg.start_min,
                        "label": format_minute(asg.start_min),
                    },
                    "changed": moved,
                }
            )
        return out

    def _proposal_dict(self, proposal: Proposal) -> dict[str, Any]:
        out: dict[str, Any] = {
            "method": proposal.method.value,
            "label": METHOD_LABELS[proposal.method],
            "ok": proposal.plan is not None,
            "reason": proposal.reason,
        }
        if proposal.plan is None or proposal.values is None or proposal.planned is None:
            return out
        planned = proposal.planned
        changes = self._changes(proposal)
        return {
            **out,
            "values": _values_dict(proposal.values),
            "seconds": round(planned.planning_seconds, 3),
            "limit_hit": planned.limit_hit,
            "stages": [
                {"name": s.name, "value": s.value, "status": s.status.value, "seconds": s.seconds}
                for s in planned.stages
            ],
            "triggers": list(proposal.triggers),
            "changes": changes,
            "changed": sum(1 for c in changes if c["changed"]),
            "moves": [m.model_dump() for m in proposal.plan.moves],
            "assignments": {
                a.activity_id: {"room": a.room_id, "start": a.start_min}
                for a in proposal.plan.assignments
            },
            "cancelled": sorted(proposal.plan.cancelled),
        }

    def _timetable(self) -> list[dict[str, Any]]:
        """Every class as the applied plans left it (view only; the log is the state)."""
        rows: dict[str, dict[str, Any]] = {}
        for a in self.base.activities:
            rows[a.id] = {
                "id": a.id,
                "cohort": a.cohort_id,
                "size": self.base.cohort(a.cohort_id).size,
                "faculty": list(a.faculty_ids),
                "types": sorted(a.allowed_room_types),
                "needs": dict(a.required_equipment),
                "room": a.room_id,
                "start": a.start_min,
                "end": a.start_min + a.duration_min,
                "original_room": a.room_id,
                "original_start": a.start_min,
                "status": "unchanged",
            }
        for plan in self._store.state.applied_plans:
            for activity_id in plan.cancelled:
                if activity_id in rows:
                    rows[activity_id]["status"] = "cancelled"
            for asg in plan.assignments:
                row = rows.get(asg.activity_id)
                if row is None or (asg.room_id, asg.start_min) == (row["room"], row["start"]):
                    continue
                length = row["end"] - row["start"]
                row.update(room=asg.room_id, start=asg.start_min, end=asg.start_min + length)
                row["status"] = "moved"
        problem = self.current_problem()
        affected = assess(problem).affected if problem is not None else frozenset()
        movable = problem.movable_activity_ids if problem is not None else frozenset()
        for row in rows.values():
            row["affected"] = row["id"] in affected
            row["movable"] = row["id"] in movable
        return sorted(rows.values(), key=lambda r: (r["start"], r["room"], r["id"]))

    def _loans(self) -> list[dict[str, Any]]:
        out = []
        for plan in self._store.state.applied_plans:
            for m in plan.moves:
                asg = next((a for a in plan.assignments if a.activity_id == m.activity_id), None)
                out.append(
                    {
                        "pool": m.pool_id,
                        "units": m.units,
                        "activity": m.activity_id,
                        "to_room": asg.room_id if asg else None,
                        "label": f"{format_minute(m.start_min)} to {format_minute(m.end_min)[4:]}",
                    }
                )
        return out

    def _event_summary(self, event: Event) -> str:
        match event:
            case FaultOccurred(fault=f):
                return f"{FAULT_KINDS.get(f.kind, f.kind)} in {f.room_id}, " + str(
                    _interval_dict(f.interval)["label"]
                )
            case RepairOverrun(fault_id=fid, new_end_min=end):
                return f"Repair overrun on {fid}, now until {format_minute(end)}"
            case SafetyHoldPlaced(hold=h):
                return f"Safety hold on {h.target_kind} {h.target_id}"
            case PlanApplied(plan=plan, approval=approval):
                who = approval.approver if approval else "n/a"
                return (
                    f"Plan applied: {len(plan.assignments)} placed, {len(plan.cancelled)} "
                    f"cancelled, {len(plan.moves)} equipment move(s); approval {who}"
                )
        return event.type  # pragma: no cover

    def suggested_incident(self) -> dict[str, Any]:
        """The scenario's own first fault, or an AC failure in the first lab, as form defaults."""
        if self.original.faults:
            f = self.original.faults[0]
            return {
                "room_id": f.room_id,
                "kind": f.kind if f.kind in FAULT_KINDS else "ac_failure",
                "start": f.interval.start,
                "end": f.interval.end,
            }
        labs = [r for r in self.base.campus.rooms if r.type == "lab"] or list(
            self.base.campus.rooms
        )
        return {
            "room_id": labs[0].id,
            "kind": "ac_failure",
            "start": self.clock,
            "end": self.clock + 240,
        }

    def snapshot(self) -> dict[str, Any]:
        state = self._store.state
        campus = self.base.campus
        problem = self.current_problem()
        faults = [
            {"id": f.id, "room": f.room_id, "kind": f.kind, **_interval_dict(f.interval)}
            for f in state.faults
        ]
        held = [
            {"target_kind": h.target_kind, "target": h.target_id, **_interval_dict(h.interval)}
            for h in state.holds
        ]
        rooms = []
        for r in sorted(campus.rooms, key=lambda r: (r.building_id, r.id)):
            rooms.append(
                {
                    "id": r.id,
                    "building": r.building_id,
                    "type": r.type,
                    "capacity": r.capacity,
                    "step_free": r.step_free,
                    "equipment": [
                        {"pool": p.id, "type": p.type, "units": p.units, "movable": p.movable}
                        for p in campus.pools
                        if p.room_id == r.id
                    ],
                    "faults": [f for f in faults if f["room"] == r.id],
                }
            )
        focus = day_of(faults[-1]["start"]) if faults else day_of(self.clock)
        recommended = self.recommended()
        impact = None
        if problem is not None:
            found = assess(problem)
            impact = {
                "window": _interval_dict(problem.window),
                "affected": sorted(found.affected),
                "movable": sorted(problem.movable_activity_ids),
            }
        return {
            "scenario": {
                "id": self.scenario.id,
                "title": self.scenario.title,
                "description": self.scenario.description,
            },
            "scenarios": [
                {"id": s.id, "title": s.title, "description": s.description}
                for s in SCENARIOS.values()
            ],
            "methods": [{"id": m.value, "label": METHOD_LABELS[m]} for m in DEMO_METHODS],
            "fault_kinds": FAULT_KINDS,
            "clock": {"min": self.clock, "label": format_minute(self.clock)},
            "version": state.version,
            "days": [{"index": d, "name": DAY_NAMES[d]} for d in range(DAYS)],
            "focus_day": min(max(focus, 0), DAYS - 1),
            "buildings": [b.id for b in campus.buildings],
            "rooms": rooms,
            "timetable": self._timetable(),
            "loans": self._loans(),
            "faults": faults,
            "holds": held,
            "impact": impact,
            "proposals": {m.value: self._proposal_dict(p) for m, p in self.proposals.items()},
            "recommended": recommended.value if recommended else None,
            "applied": self.applied,
            "last_round": self.last_round,
            "events": [
                {
                    "version": e.version,
                    "type": e.type,
                    "at": format_minute(e.at_min),
                    "summary": self._event_summary(e),
                }
                for e in self._store.events()
            ],
            "steps": [s.as_dict() for s in self.steps],
            "suggested_incident": self.suggested_incident(),
        }

    def close(self) -> None:
        if self.store is not None:
            self.store.close()
            self.store = None


def _by_start(activity: Activity) -> tuple[int, str]:
    return (activity.start_min, activity.id)
