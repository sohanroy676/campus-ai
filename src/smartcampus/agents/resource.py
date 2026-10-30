"""Resource (room) agents: each room bids for a class with its cheapest placement.

The cost of a bid is the solver's own per-placement costs in the order P, D, K, S, T
(`solver/objective.py`), so every method ranks placements the same way. An agent proposes; the
manager decides whether a proposal keeps the plan valid (`rules/validator`).
"""

from dataclasses import dataclass

from smartcampus.agents.equipment import propose_moves
from smartcampus.domain.entities import Activity, Room
from smartcampus.domain.plan import Assignment, EquipmentMove
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import valid_starts
from smartcampus.solver.objective import (
    delay_minutes,
    move_cost,
    people_cost,
    shift_minutes,
    tie_break_cost,
)

type Cost = tuple[int, int, int, int, int]


@dataclass(frozen=True)
class Bid:
    activity_id: str
    room_id: str
    start_min: int
    moves: tuple[EquipmentMove, ...]
    cost: Cost

    @property
    def assignment(self) -> Assignment:
        return Assignment(
            activity_id=self.activity_id, room_id=self.room_id, start_min=self.start_min
        )


def bid_cost(
    problem: RecoveryProblem,
    activity: Activity,
    room: Room,
    start: int,
    moves: tuple[EquipmentMove, ...],
) -> Cost:
    return (
        people_cost(problem, activity, room.id, start),
        delay_minutes(activity, start),
        sum(move_cost(problem, problem.campus.pool(m.pool_id), m.units, room.id) for m in moves),
        shift_minutes(activity, start),
        tie_break_cost(problem, activity, room.id, start),
    )


class RoomAgent:
    """Bids for a class in one room."""

    def __init__(self, room: Room) -> None:
        self.room = room

    def bids(self, problem: RecoveryProblem, activity: Activity) -> list[Bid]:
        """Every placement in this room with the moves it needs, cheapest first."""
        out: list[Bid] = []
        for start in valid_starts(problem, activity):
            moves = propose_moves(problem, activity, self.room, start)
            if moves is not None:
                cost = bid_cost(problem, activity, self.room, start, moves)
                out.append(Bid(activity.id, self.room.id, start, moves, cost))
        return sorted(out, key=lambda b: (b.cost, b.start_min))
