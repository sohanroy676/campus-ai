"""R4 room_type_and_equipment: allowed room type, and enough usable equipment units.

Units present in the room (pools on hold excluded) plus units moved in from other rooms must cover
each required equipment type. Pools with `movable = false` never move. A moved unit is unavailable
at its source room from the move start until the borrowing class ends plus the return trip, so at
every moment the units in use at home plus the units lent out fit the stock of that room and type.
"""

from collections import Counter, defaultdict

from ortools.sat.python import cp_model

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    WEEK_END_MIN,
    Placement,
    contention_capacity,
    counts_as_moved_in,
    home_use,
    known_moves,
    lent_until,
    move_minutes,
    placements,
    plan_placements,
    remaining_equipment_need,
    return_minutes,
)
from smartcampus.rules.base import RuleId, Violation
from smartcampus.rules.variables import DecisionVars


def has_wrong_type(placement: Placement) -> bool:
    return placement.room.type not in placement.activity.allowed_room_types


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out: list[Violation] = []
    moves = known_moves(problem, plan)
    for p in placements(problem, plan):
        if has_wrong_type(p):
            out.append(
                Violation(
                    RuleId.R4,
                    f"room {p.room.id} is a {p.room.type}, not allowed for {p.activity.id}",
                    (p.activity.id,),
                    (p.room.id,),
                )
            )
        for eq_type, missing in sorted(remaining_equipment_need(problem, p).items()):
            moved_in = sum(
                m.units
                for m, pool, act in moves
                if act.id == p.activity.id and counts_as_moved_in(pool, eq_type, p.room.id)
            )
            if moved_in < missing:
                out.append(
                    Violation(
                        RuleId.R4,
                        f"{p.activity.id} in {p.room.id} lacks {missing - moved_in} unit(s) "
                        f"of {eq_type}",
                        (p.activity.id,),
                        (p.room.id,),
                    )
                )
    pools = {pool.id for pool in problem.campus.pools}
    for m in plan.moves:
        if m.pool_id not in pools:
            out.append(Violation(RuleId.R4, f"move of unknown pool {m.pool_id}", (m.activity_id,)))
        elif m.activity_id not in problem.movable_activity_ids:
            out.append(
                Violation(
                    RuleId.R4, f"move for unaffected activity {m.activity_id}", (m.activity_id,)
                )
            )
    for (pool_id, activity_id), n in sorted(
        Counter((m.pool_id, m.activity_id) for m in plan.moves).items()
    ):
        if n > 1:
            out.append(
                Violation(
                    RuleId.R4,
                    f"{n} moves of pool {pool_id} for {activity_id}; at most one is allowed",
                    (activity_id,),
                )
            )
    for m, pool, act in moves:
        if not pool.movable:
            out.append(Violation(RuleId.R4, f"pool {pool.id} is not movable", (act.id,)))
        if m.units > pool.units:
            out.append(
                Violation(
                    RuleId.R4,
                    f"move of {m.units} units exceeds the {pool.units} in pool {pool.id}",
                    (act.id,),
                )
            )
    out.extend(_contention_violations(problem, plan))
    return out


def _contention_violations(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    """Per (room, type): units in use at home plus units lent out must fit the stock."""
    out: list[Violation] = []
    placed = plan_placements(problem, plan)
    busy: dict[tuple[str, str], list[tuple[int, int, int]]] = defaultdict(list)
    for p in placements(problem, plan):
        for eq_type, units in home_use(problem, p).items():
            busy[(p.room.id, eq_type)].append((p.start, p.end, units))
    for m, pool, act in known_moves(problem, plan):
        class_ends = {q.end for q in placed if q.activity.id == act.id}
        if len(class_ends) != 1:
            out.append(
                Violation(
                    RuleId.R4,
                    f"move of {pool.id} for {act.id} needs exactly one placed class, "
                    f"found {len(class_ends)} end time(s)",
                    (act.id,),
                )
            )
            continue
        until = lent_until(m.start_min, class_ends.pop(), pool, m.units)
        busy[(pool.room_id, pool.type)].append((m.start_min, until, m.units))
    stock = contention_capacity(problem)
    for (room_id, eq_type), intervals in sorted(busy.items()):
        for start in sorted({s for s, _, _ in intervals}):
            load = sum(units for s, e, units in intervals if s <= start < e)
            if load > stock.get((room_id, eq_type), 0):
                out.append(
                    Violation(
                        RuleId.R4,
                        f"{eq_type} in {room_id}: {load} unit(s) in use or lent out at minute "
                        f"{start}, only {stock.get((room_id, eq_type), 0)} in stock",
                        (),
                        (room_id,),
                    )
                )
    return out


def post(ctx: DecisionVars) -> None:
    lit = ctx.rule_lit[RuleId.R4]
    pools = ctx.problem.campus.pools
    barred: list[cp_model.IntVar] = []  # placements R4 never allows
    fixed_barred = False  # a fixed placement R4 does not allow
    # Placements that need moved units, grouped by (class, room, type, units missing).
    short: dict[tuple[str, str, str, int], list[Placement]] = defaultdict(list)
    for option in ctx.all_options():
        blocked = has_wrong_type(option)
        for eq_type, missing in remaining_equipment_need(ctx.problem, option).items():
            # Unaffected activities cannot get moved units.
            if option.var is None or not any(
                counts_as_moved_in(p, eq_type, option.room.id) for p in pools
            ):
                blocked = True
            else:
                short[option.activity.id, option.room.id, eq_type, missing].append(option)
        if blocked and option.var is None:
            fixed_barred = True
        elif blocked and option.var is not None:
            barred.append(option.var)
    if fixed_barred:
        ctx.model.add_bool_or([lit.negated()])
    if barred:
        ctx.model.add(cp_model.LinearExpr.sum(barred) == 0).only_enforce_if(lit)
    for (activity_id, room_id, eq_type, missing), group in short.items():
        happens = ctx.any_happens(("short", activity_id, room_id, eq_type, missing), group)
        moved_in = [
            ctx.units[(activity_id, p.id)] for p in pools if counts_as_moved_in(p, eq_type, room_id)
        ]
        assert happens is not None  # every member has a variable
        ctx.model.add(cp_model.LinearExpr.sum(moved_in) >= missing).only_enforce_if([happens, lit])
    for (_, pool_id), units in ctx.units.items():
        if not ctx.problem.campus.pool(pool_id).movable:
            ctx.model.add(units == 0).only_enforce_if(lit)
    _post_contention(ctx)


def _post_contention(ctx: DecisionVars) -> None:
    """One cumulative per (room, type): home use and lent-out units against the stock."""
    model, problem = ctx.model, ctx.problem
    lit = ctx.rule_lit[RuleId.R4]
    longest = max((move_minutes(p, p.units) for p in problem.campus.pools), default=0)
    horizon = WEEK_END_MIN + longest
    for (room_id, eq_type), stock in contention_capacity(problem).items():
        intervals = []
        demands: list[cp_model.LinearExprT] = []
        for option in ctx.all_options():
            use = home_use(problem, option).get(eq_type, 0)
            if option.room.id != room_id or use == 0:
                continue
            present = lit if option.var is None else ctx.and_literal(option.var, lit)
            intervals.append(
                model.new_optional_fixed_size_interval_var(
                    option.start, option.activity.duration_min, present, f"home_{room_id}"
                )
            )
            demands.append(use)
        for key, units in ctx.units.items():
            pool = problem.campus.pool(key[1])
            if (pool.room_id, pool.type) != (room_id, eq_type):
                continue
            moved, start = ctx.moved[key], ctx.move_start[key]
            placed = ctx.placed_literal(key[0])
            if placed is not None:
                model.add_bool_or([placed, moved.negated()]).only_enforce_if(lit)
            back = model.new_int_var(0, horizon, f"back_{key[0]}_{key[1]}")
            # back = class end + return trip, for every chosen start: between earliest and latest
            earliest, latest = ctx.start_bounds(key[0])
            trip = problem.activity(key[0]).duration_min + return_minutes(pool, units)
            model.add(back >= latest + trip).only_enforce_if([moved, lit])
            model.add(back <= earliest + trip).only_enforce_if([moved, lit])
            until = model.new_int_var(0, horizon, f"until_{key[0]}_{key[1]}")
            model.add_max_equality(until, [start, back])  # never earlier than the move start
            length = model.new_int_var(0, horizon, f"lent_{key[0]}_{key[1]}")
            model.add(length == until - start)
            intervals.append(
                model.new_optional_interval_var(
                    start, length, until, ctx.and_literal(moved, lit), f"lent_{key[0]}_{key[1]}"
                )
            )
            demands.append(units)
        if intervals:
            model.add_cumulative(intervals, demands, stock)
