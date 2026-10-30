"""R1 and R2 `check` after indexing against the earlier loops: same violations, same order.

The plans are the greedy plan and edited copies (everything stacked into one room at one start,
shifted off the slot grid, moved to an unknown room, assigned twice and also cancelled) so that
each kind of violation shows up.
"""

from collections import Counter
from pathlib import Path

import pytest

from smartcampus.baselines.greedy import greedy
from smartcampus.domain.plan import Assignment, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.generator.scenario import load_scenario
from smartcampus.rules import r1_assignment as r1
from smartcampus.rules import r2_room_conflict as r2
from smartcampus.rules._shared import intervals_overlap, placements, valid_starts
from smartcampus.rules.base import RuleId, Violation

# The original 12 small ones (loads 50 and 75, seeds 1 and 2).
SMALL = sorted(
    (Path(__file__).parents[2] / "scenarios" / "frozen").glob("small-l[57][05]-*-s[12].json")
)


def r1_before_indexing(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out: list[Violation] = []
    movable = problem.movable_activity_ids
    counts = Counter(asg.activity_id for asg in plan.assignments)
    for activity_id in sorted(movable):
        placed, cancelled = counts[activity_id], activity_id in plan.cancelled
        if placed + cancelled == 1:
            continue
        if placed == 0:
            reason = "is neither assigned nor cancelled"
        elif cancelled:
            reason = "is both assigned and cancelled"
        else:
            reason = f"is assigned {placed} times"
        out.append(Violation(RuleId.R1, f"activity {activity_id} {reason}", (activity_id,)))
    for activity_id in sorted((set(counts) | plan.cancelled) - movable):
        out.append(
            Violation(
                RuleId.R1, f"activity {activity_id} is not an affected activity", (activity_id,)
            )
        )
    rooms = {r.id for r in problem.campus.rooms}
    for asg in plan.assignments:
        if asg.activity_id not in movable:
            continue
        if asg.room_id not in rooms:
            out.append(
                Violation(
                    RuleId.R1, f"unknown room {asg.room_id}", (asg.activity_id,), (asg.room_id,)
                )
            )
        elif asg.start_min not in valid_starts(problem, problem.activity(asg.activity_id)):
            out.append(
                Violation(
                    RuleId.R1,
                    f"activity {asg.activity_id} cannot start at minute {asg.start_min}: "
                    "not a slot inside the recovery window and a teaching day",
                    (asg.activity_id,),
                    (asg.room_id,),
                )
            )
    return out


def r2_before_indexing(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out: list[Violation] = []
    found = placements(problem, plan)
    for i, p in enumerate(found):
        if r2.is_closed(problem, p):
            out.append(
                Violation(
                    RuleId.R2,
                    f"room {p.room.id} is closed while {p.activity.id} is held there",
                    (p.activity.id,),
                    (p.room.id,),
                )
            )
        for q in found[i + 1 :]:
            if p.room.id == q.room.id and intervals_overlap(p.start, p.end, q.start, q.end):
                ids = tuple(sorted((p.activity.id, q.activity.id)))
                out.append(
                    Violation(
                        RuleId.R2,
                        f"room {p.room.id} hosts {ids[0]} and {ids[1]} at the same time",
                        ids,
                        (p.room.id,),
                    )
                )
    return out


def variants(problem: RecoveryProblem, plan: Plan) -> list[Plan]:
    rooms = sorted(r.id for r in problem.campus.rooms)
    first_start = min((a.start_min for a in plan.assignments), default=0)

    def with_assignments(assignments: list[Assignment], **update: object) -> Plan:
        return plan.model_copy(update={"assignments": tuple(assignments), **update})

    stacked = [
        a.model_copy(update={"room_id": rooms[0], "start_min": first_start})
        for a in plan.assignments
    ]
    off_grid = [a.model_copy(update={"start_min": a.start_min + 7}) for a in plan.assignments]
    elsewhere = [a.model_copy(update={"room_id": "no-such-room"}) for a in plan.assignments[:3]]
    twice = [*plan.assignments, *plan.assignments[:2]]
    both = {a.activity_id for a in plan.assignments[:2]} | set(plan.cancelled)
    return [
        plan,
        with_assignments(stacked),
        with_assignments(off_grid),
        with_assignments([*elsewhere, *plan.assignments[3:]]),
        with_assignments(twice),
        with_assignments(list(plan.assignments), cancelled=frozenset(both)),
        with_assignments([]),
    ]


@pytest.mark.parametrize("path", SMALL, ids=lambda p: p.stem)
def test_indexed_checks_match_the_earlier_loops(path: Path) -> None:
    problem = load_scenario(path)
    r1_seen = r2_seen = 0
    for plan in variants(problem, greedy(problem)):
        expected_r1, expected_r2 = (
            r1_before_indexing(problem, plan),
            r2_before_indexing(problem, plan),
        )
        assert r1.check(problem, plan) == expected_r1
        assert r2.check(problem, plan) == expected_r2
        r1_seen += len(expected_r1)
        r2_seen += len(expected_r2)
    assert r1_seen > 0 and r2_seen > 0, "variants should produce violations of both rules"
