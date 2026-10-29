"""Greedy baseline: one class at a time, each takes the cheapest placement that keeps validity.

Classes are handled in order of original start. For each one every (room, start) is ranked by the
solver's own per-placement costs in the order P, D, K, S, T (`solver/objective.py`), then tried in
that order until the validator accepts it. Classes not yet handled count as cancelled during the
check, which can only relax the rules, so an accepted placement never breaks an earlier one.
A class with no valid placement is cancelled. The baseline never looks ahead: an early class can
take the only room a later class needed.
"""

from smartcampus.domain.entities import Activity, Room
from smartcampus.domain.plan import Assignment, EquipmentMove, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    Placement,
    counts_as_moved_in,
    earliest_borrow_start,
    move_minutes,
    remaining_equipment_need,
    valid_starts,
)
from smartcampus.rules.validator import validate
from smartcampus.solver.explain import explain_infeasibility
from smartcampus.solver.objective import (
    crosses_buildings,
    delay_minutes,
    move_cost,
    people_cost,
    shift_minutes,
    tie_break_cost,
)
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
            new_moves = _moves_for(problem, activity, room, start)
            if new_moves is None:
                continue
            cost = (
                people_cost(problem, activity, room.id, start),
                delay_minutes(activity, start),
                sum(
                    move_cost(problem, problem.campus.pool(m.pool_id), m.units, room.id)
                    for m in new_moves
                ),
                shift_minutes(activity, start),
                tie_break_cost(problem, activity, room.id, start),
            )
            out.append((cost, room, start, new_moves))
    return sorted(out, key=lambda c: (c[0], c[1].id, c[2]))


def _moves_for(
    problem: RecoveryProblem, activity: Activity, room: Room, start: int
) -> tuple[EquipmentMove, ...] | None:
    """Moves that bring the missing equipment to `room` just before `start`; None if impossible."""
    placement = Placement(activity, room, start)
    moves: list[EquipmentMove] = []
    for equipment_type, missing in sorted(remaining_equipment_need(problem, placement).items()):
        pools = sorted(
            (
                p
                for p in problem.campus.pools
                if p.movable and counts_as_moved_in(p, equipment_type, room.id)
            ),
            key=lambda p: (crosses_buildings(problem, p, room.id), p.move_minutes_per_unit, p.id),
        )
        for pool in pools:
            if missing == 0:
                break
            units = min(missing, pool.units)
            move_start = start - move_minutes(pool, units)
            hold_ends = earliest_borrow_start(problem, pool.id, placement.end)
            if move_start < problem.plan_time_min or (
                hold_ends is not None and move_start < hold_ends
            ):
                continue
            moves.append(
                EquipmentMove(
                    pool_id=pool.id,
                    activity_id=activity.id,
                    units=units,
                    start_min=move_start,
                    end_min=start,
                )
            )
            missing -= units
        if missing:
            return None
    return tuple(moves)
