"""The lexicographic objective (docs/model-spec.md section 4): C, P, D, K, S, T.

Per-placement costs are plain functions used twice: `evaluate` scores a finished plan, and
`stage_expressions` turns the same costs into CP-SAT linear expressions over the decision variables.
"""

from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from smartcampus.domain.entities import Activity, EquipmentPool
from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import known_moves, move_minutes, plan_placements
from smartcampus.rules.variables import DecisionVars

REPEAT_MOVE_PENALTY = 50
LATE_CHANGE_MIN = 30
CROSS_BUILDING_MOVE_COST = 20
BUILDING_CHANGE_PENALTY = 1000


@dataclass(frozen=True, order=True)
class StageValues:
    """Stage values in solving order; comparing two of them is the lexicographic comparison."""

    cancellations: int
    people_moved: int
    delay: int
    cost: int
    start_shift: int
    tie_break: int


def is_changed(activity: Activity, room_id: str, start: int) -> bool:
    return (room_id, start) != (activity.room_id, activity.start_min)


def lateness_factor(problem: RecoveryProblem, activity: Activity) -> int:
    """2 when the change lands less than 30 minutes before the original start."""
    return 2 if activity.start_min - problem.plan_time_min < LATE_CHANGE_MIN else 1


def people_cost(problem: RecoveryProblem, activity: Activity, room_id: str, start: int) -> int:
    if not is_changed(activity, room_id, start):
        return 0
    people = problem.cohort(activity.cohort_id).size + len(activity.faculty_ids)
    return people * lateness_factor(problem, activity)


def repeat_moves(problem: RecoveryProblem, cohort_id: str, changed: int) -> int:
    """Moves of a cohort that count as a second or later move this week."""
    if problem.prior_moves_this_week.get(cohort_id, 0) >= 1:
        return changed
    return max(0, changed - 1)


def delay_minutes(activity: Activity, start: int) -> int:
    return max(0, start - activity.start_min)


def shift_minutes(activity: Activity, start: int) -> int:
    """Minutes between the new and the original start, in either direction."""
    return abs(start - activity.start_min)


def changes_building(problem: RecoveryProblem, activity: Activity, room_id: str) -> bool:
    campus = problem.campus
    return campus.room(room_id).building_id != campus.room(activity.room_id).building_id


def room_rank(problem: RecoveryProblem, room_id: str) -> int:
    """Position of the room id among all room ids sorted alphabetically."""
    return sorted(r.id for r in problem.campus.rooms).index(room_id)


def tie_break_cost(problem: RecoveryProblem, activity: Activity, room_id: str, start: int) -> int:
    if not is_changed(activity, room_id, start):
        return 0
    building = BUILDING_CHANGE_PENALTY if changes_building(problem, activity, room_id) else 0
    return building + room_rank(problem, room_id)


def crosses_buildings(problem: RecoveryProblem, pool: EquipmentPool, room_id: str) -> bool:
    campus = problem.campus
    return campus.room(pool.room_id).building_id != campus.room(room_id).building_id


def evaluate(problem: RecoveryProblem, plan: Plan) -> StageValues:
    """Stage values of a plan that passes the validator (one placement per affected class)."""
    placed = {p.activity.id: p for p in plan_placements(problem, plan)}
    affected = [a for a in problem.activities if a.id in problem.movable_activity_ids]
    cancellations = sum(a.id in plan.cancelled for a in affected)
    people = delay = start_shift = tie_break = 0
    changed_by_cohort: dict[str, int] = defaultdict(int)
    for activity in affected:
        if (p := placed.get(activity.id)) is None:
            continue
        people += people_cost(problem, activity, p.room.id, p.start)
        delay += delay_minutes(activity, p.start)
        start_shift += shift_minutes(activity, p.start)
        tie_break += tie_break_cost(problem, activity, p.room.id, p.start)
        changed_by_cohort[activity.cohort_id] += is_changed(activity, p.room.id, p.start)
    people += REPEAT_MOVE_PENALTY * sum(
        repeat_moves(problem, cohort_id, count) for cohort_id, count in changed_by_cohort.items()
    )
    cost = 0
    for m, pool, activity in known_moves(problem, plan):
        cost += move_minutes(pool, m.units)
        if (p := placed.get(activity.id)) is not None and crosses_buildings(
            problem, pool, p.room.id
        ):
            cost += CROSS_BUILDING_MOVE_COST
    return StageValues(cancellations, people, delay, cost, start_shift, tie_break)


def _weighted(terms: list[tuple[int, cp_model.IntVar]]) -> cp_model.LinearExprT:
    return cp_model.LinearExpr.weighted_sum([v for _, v in terms], [c for c, _ in terms])


def stage_expressions(ctx: DecisionVars) -> list[cp_model.LinearExprT]:
    """The six stage expressions, in solving order, over the decision variables of `ctx`."""
    problem, model = ctx.problem, ctx.model
    affected = [a for a in problem.activities if a.id in problem.movable_activity_ids]

    people: list[tuple[int, cp_model.IntVar]] = []
    delay: list[tuple[int, cp_model.IntVar]] = []
    start_shift: list[tuple[int, cp_model.IntVar]] = []
    tie_break: list[tuple[int, cp_model.IntVar]] = []
    changed_by_cohort: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    for activity in affected:
        for option in ctx.options[activity.id]:
            if option.var is None:
                continue
            room_id, start = option.room.id, option.start
            people.append((people_cost(problem, activity, room_id, start), option.var))
            delay.append((delay_minutes(activity, start), option.var))
            start_shift.append((shift_minutes(activity, start), option.var))
            tie_break.append((tie_break_cost(problem, activity, room_id, start), option.var))
            if is_changed(activity, room_id, start):
                changed_by_cohort[activity.cohort_id].append(option.var)

    for cohort_id, changed in changed_by_cohort.items():
        if problem.prior_moves_this_week.get(cohort_id, 0) >= 1:
            people.extend((REPEAT_MOVE_PENALTY, var) for var in changed)
        else:
            extra = model.new_int_var(0, len(changed), f"repeats_{cohort_id}")
            model.add_max_equality(extra, [0, cp_model.LinearExpr.sum(changed) - 1])
            people.append((REPEAT_MOVE_PENALTY, extra))

    cost: list[tuple[int, cp_model.IntVar]] = []
    for (activity_id, pool_id), units in ctx.units.items():
        pool = problem.campus.pool(pool_id)
        moved = ctx.moved[(activity_id, pool_id)]
        minutes = model.new_int_var(
            0, move_minutes(pool, pool.units), f"staff_{activity_id}_{pool_id}"
        )
        model.add(minutes == move_minutes(pool, units)).only_enforce_if(moved)
        model.add(minutes == 0).only_enforce_if(moved.negated())
        cost.append((1, minutes))
        far = [
            o.var
            for o in ctx.options[activity_id]
            if o.var is not None and crosses_buildings(problem, pool, o.room.id)
        ]
        if far:
            lands_far = model.new_bool_var(f"far_{activity_id}_{pool_id}")
            model.add_max_equality(lands_far, far)
            cost.append((CROSS_BUILDING_MOVE_COST, ctx.and_literal(moved, lands_far)))

    return [
        cp_model.LinearExpr.sum(list(ctx.cancelled.values())),
        _weighted(people),
        _weighted(delay),
        _weighted(cost),
        _weighted(start_shift),
        _weighted(tie_break),
    ]
