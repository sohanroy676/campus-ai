"""R6 `check` indexed by person against the old all-pairs loop: same violations, same order.

The plans are the greedy plan plus a shifted copy (every class one slot later, then everything at
the same start) so that overlaps and far back-to-back pairs actually show up.
"""

from pathlib import Path

import pytest

from smartcampus.baselines.greedy import greedy
from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.generator.scenario import load_scenario
from smartcampus.rules import r6_people_conflict as r6
from smartcampus.rules._shared import MAX_BACK_TO_BACK_TRAVEL_MIN, intervals_overlap, placements
from smartcampus.rules.base import RuleId, Violation

# The original 12 small ones (loads 50 and 75, seeds 1 and 2): the old all-pairs check is slow.
SMALL = sorted(
    (Path(__file__).parents[2] / "scenarios" / "frozen").glob("small-l[57][05]-*-s[12].json")
)


def check_all_pairs(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    """The R6 check before indexing."""
    out: list[Violation] = []
    found = placements(problem, plan)
    for i, p in enumerate(found):
        for q in found[i + 1 :]:
            if not r6.shares_person(p, q):
                continue
            ids = tuple(sorted((p.activity.id, q.activity.id)))
            rooms = tuple(sorted({p.room.id, q.room.id}))
            if intervals_overlap(p.start, p.end, q.start, q.end):
                out.append(
                    Violation(
                        RuleId.R6, f"{ids[0]} and {ids[1]} share a person and overlap", ids, rooms
                    )
                )
            elif r6.is_too_far(problem, p, q):
                out.append(
                    Violation(
                        RuleId.R6,
                        f"{ids[0]} and {ids[1]} are back-to-back with more than "
                        f"{MAX_BACK_TO_BACK_TRAVEL_MIN} minutes between buildings",
                        ids,
                        rooms,
                    )
                )
    return out


def variants(problem: RecoveryProblem, plan: Plan) -> list[Plan]:
    shifted = [a.model_copy(update={"start_min": a.start_min + 30}) for a in plan.assignments]
    first = min((a.start_min for a in plan.assignments), default=0)
    stacked = [a.model_copy(update={"start_min": first}) for a in plan.assignments]
    return [
        plan,
        plan.model_copy(update={"assignments": tuple(shifted)}),
        plan.model_copy(update={"assignments": tuple(stacked)}),
    ]


@pytest.mark.parametrize("path", SMALL, ids=lambda p: p.stem)
def test_indexed_check_matches_all_pairs(path: Path) -> None:
    problem = load_scenario(path)
    reference_seen = 0
    for plan in variants(problem, greedy(problem)):
        expected = check_all_pairs(problem, plan)
        assert r6.check(problem, plan) == expected
        reference_seen += len(expected)
    assert reference_seen > 0, "variants should produce at least one R6 violation"
