"""Contract-net: a manager announces classes, room agents bid, the manager awards (spec section 9).

Initial auction: classes are announced in order of original start; every room agent bids its
placements (cheapest first, `agents/resource.py`) and the manager awards the cheapest bid that the
validator accepts. Classes not yet awarded count as cancelled during the check, as in greedy.

Re-auction rounds (the negotiation): for each class in turn, those without an award first, the
manager withdraws its award, announces it again, and keeps the new award only if the whole plan
scores strictly better (`evaluate`, lexicographic). A class with no award may also ask awarded
classes to step aside, one at a time (the few the validator names most often when it rejects the
cheapest bids): the class takes its best bid, the displaced class bids again, and the swap stands
only if the whole plan scores strictly better. Rounds stop when a round changes nothing, after
`MAX_ROUNDS`, or at the time limit, keeping the best plan so far.

Agents only propose placements. Rules are checked by `rules.validator`, never in agents, and the
manager never writes state.
"""

import heapq
import time
from collections import Counter
from collections.abc import Iterator

from smartcampus.agents.resource import Bid, RoomAgent
from smartcampus.domain.entities import Activity
from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.validator import validate
from smartcampus.solver.explain import explain_infeasibility
from smartcampus.solver.objective import evaluate
from smartcampus.solver.solve import InfeasibleInputError

MAX_ROUNDS = 5
BLOCKER_SAMPLE = 25  # cheapest rejected bids whose violations name the classes in the way
DISPLACEMENT_TRIES = 5  # most-named classes asked to step aside, per class without a bid

type Awards = dict[str, Bid]


class _OutOfTime(Exception):
    """The wall-clock limit was reached; the awards made so far stand."""


class _Manager:
    def __init__(self, problem: RecoveryProblem, version: int, deadline: float) -> None:
        self.problem = problem
        self.version = version
        self.deadline = deadline
        self.agents = [RoomAgent(r) for r in sorted(problem.campus.rooms, key=lambda r: r.id)]
        self.order = sorted(
            (problem.activity(a) for a in problem.movable_activity_ids),
            key=lambda a: (a.start_min, a.id),
        )
        self.awards: Awards = {}
        self.blockers: Counter[str] = Counter()  # how often the last rejected bids name each class

    def plan(self, awards: Awards) -> Plan:
        return Plan(
            based_on_version=self.version,
            assignments=tuple(b.assignment for b in awards.values()),
            cancelled=frozenset(a.id for a in self.order) - awards.keys(),
            moves=tuple(m for b in awards.values() for m in b.moves),
        )

    def best_bid(self, activity: Activity, awards: Awards) -> Bid | None:
        """The cheapest bid over all rooms that keeps the plan valid (ties: room id, then start)."""
        merged: Iterator[Bid] = heapq.merge(
            *(agent.bids(self.problem, activity) for agent in self.agents),
            key=lambda b: (b.cost, b.room_id, b.start_min),
        )
        self.blockers = Counter()
        rejected = 0
        for bid in merged:
            if time.monotonic() >= self.deadline:
                raise _OutOfTime
            violations = validate(self.problem, self.plan({**awards, activity.id: bid}))
            if not violations:
                return bid
            if rejected < BLOCKER_SAMPLE:
                rejected += 1
                self.blockers.update({a for v in violations for a in v.activity_ids})
        return None

    def auction(self) -> None:
        for activity in self.order:
            bid = self.best_bid(activity, self.awards)
            if bid is not None:
                self.awards = {**self.awards, activity.id: bid}

    def rounds(self) -> None:
        for _ in range(MAX_ROUNDS):
            before = dict(self.awards)
            # classes without an award go first: they are where the plan can gain most
            for activity in sorted(self.order, key=lambda a: a.id in self.awards):
                self._reauction(activity)
            if self.awards == before:
                return

    def _reauction(self, activity: Activity) -> None:
        score = evaluate(self.problem, self.plan(self.awards))
        without = {k: v for k, v in self.awards.items() if k != activity.id}
        bid = self.best_bid(activity, without)
        if bid is not None:
            trial = {**without, activity.id: bid}
            if evaluate(self.problem, self.plan(trial)) < score:
                self.awards = trial
            return
        if activity.id in self.awards:
            return
        named = [(n, a) for a, n in self.blockers.items() if a in self.awards]
        asked = [a for _, a in sorted(named, key=lambda t: (-t[0], t[1]))[:DISPLACEMENT_TRIES]]
        for other in (self.problem.activity(a) for a in asked):
            swapped = self._displace(activity, other)
            if swapped is not None and evaluate(self.problem, self.plan(swapped)) < score:
                self.awards = swapped
                return

    def _displace(self, activity: Activity, other: Activity) -> Awards | None:
        """Awards where `activity` takes a bid after `other` steps aside and bids again."""
        base = {k: v for k, v in self.awards.items() if k != other.id}
        first = self.best_bid(activity, base)
        if first is None:
            return None
        trial = {**base, activity.id: first}
        again = self.best_bid(other, trial)
        return trial if again is None else {**trial, other.id: again}


def contract_net(
    problem: RecoveryProblem, *, time_limit_seconds: float, based_on_version: int = 0
) -> Plan:
    """A valid plan, or `InfeasibleInputError` if the input already breaks a hard rule.

    At the time limit the awards made so far are returned, the rest cancelled.
    """
    manager = _Manager(problem, based_on_version, time.monotonic() + time_limit_seconds)
    try:
        manager.auction()
        manager.rounds()
    except _OutOfTime:
        pass
    plan = manager.plan(manager.awards)
    if validate(problem, plan):
        raise InfeasibleInputError(explain_infeasibility(problem))
    return plan
