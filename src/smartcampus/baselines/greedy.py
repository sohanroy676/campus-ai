"""Greedy baseline: one class at a time, each takes the cheapest placement that keeps validity.

Classes are handled in order of original start. For each one every (room, start) is ranked by the
solver's own per-placement costs in the order P, D, K, S, T (`solver/objective.py`), then tried in
that order until the validator accepts it. Classes not yet handled count as cancelled during the
check, which can only relax the rules, so an accepted placement never breaks an earlier one.
A class with no valid placement is cancelled. The baseline never looks ahead: an early class can
take the only room a later class needed.
"""

from smartcampus.agents.equipment import propose_moves
from smartcampus.agents.resource import bid_cost
from smartcampus.domain.entities import Activity, Room
from smartcampus.domain.plan import Assignment, EquipmentMove, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import valid_starts
from smartcampus.rules.validator import validate
from smartcampus.solver.explain import explain_infeasibility
from smartcampus.solver.solve import InfeasibleInputError

type Candidate = tuple[tuple[int, ...], Room, int, tuple[EquipmentMove, ...]]


def greedy(problem: RecoveryProblem, *, based_on_version: int = 0, random_seed: int = 42) -> Plan:
    """A valid plan, or `InfeasibleInputError` if the input already breaks a hard rule."""
    order = sorted(
        (problem.activity(a) for a in problem.movable_activity_ids),
        key=lambda a: (a.start_min, a.id),
    )
    pending = {a.id for a in order}
    assignments: list[Assignment] = []
    moves: list[EquipmentMove] = []
    cancelled: set[str] = set()

    def plan_with(extra: Assignment | None, extra_moves: tuple[EquipmentMove, ...]) -> Plan:
        return Plan(
            based_on_version=based_on_version,
            assignments=(*assignments, *([extra] if extra else [])),
            cancelled=frozenset(pending | cancelled),
            moves=(*moves, *extra_moves),
        )

    for activity in order:
        pending.discard(activity.id)
        for _, room, start, new_moves in _candidates(problem, activity):
            assignment = Assignment(activity_id=activity.id, room_id=room.id, start_min=start)
            if not validate(problem, plan_with(assignment, new_moves)):
                assignments.append(assignment)
                moves.extend(new_moves)
                break
        else:
            cancelled.add(activity.id)

    plan = plan_with(None, ())
    if validate(problem, plan):
        raise InfeasibleInputError(explain_infeasibility(problem, random_seed=random_seed))
    return plan


def _candidates(problem: RecoveryProblem, activity: Activity) -> list[Candidate]:
    """Every (room, start) with its moves, cheapest first; ties go to room id, then start."""
    out: list[Candidate] = []
    for room in sorted(problem.campus.rooms, key=lambda r: r.id):
        for start in valid_starts(problem, activity):
            new_moves = propose_moves(problem, activity, room, start)
            if new_moves is None:
                continue
            out.append(
                (bid_cost(problem, activity, room, start, new_moves), room, start, new_moves)
            )
    return sorted(out, key=lambda c: (c[0], c[1].id, c[2]))
