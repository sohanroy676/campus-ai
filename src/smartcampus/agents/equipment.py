"""Equipment agent: proposes the moves that bring a class's missing equipment to a room.

It only proposes. Whether a proposal keeps the plan valid is decided by `rules/` (R4, R5), through
the validator, never here. Used by the greedy baseline and the contract-net room agents.
"""

from smartcampus.domain.entities import Activity, Room
from smartcampus.domain.plan import EquipmentMove
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    Placement,
    counts_as_moved_in,
    earliest_borrow_start,
    move_minutes,
    remaining_equipment_need,
)
from smartcampus.solver.objective import crosses_buildings


def propose_moves(
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
