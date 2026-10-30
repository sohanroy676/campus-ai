"""R4 and R5 grouped encodings against the old per-placement encodings on the generated scenarios.

The old encodings add one constraint for every (class, pool, placement). The new ones share
per-class bounds and literals (`start_bounds`, `start_literals`, `placed_literal`). For each
scenario this builds plans with equipment moves (fed, late, short, crowded, unneeded, overrun,
none), fixes every decision variable to the plan with solver hints and asks whether the model
still has a solution. The old encoding, the new one and the validator's `check` must agree.

The old code is kept here only as the reference.
"""

from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from smartcampus.domain.plan import Assignment, EquipmentMove, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.generator.scenario import load_scenario
from smartcampus.rules import r4_room_type_and_equipment as r4
from smartcampus.rules import r5_move_lead_time as r5
from smartcampus.rules._shared import (
    WEEK_END_MIN,
    Placement,
    contention_capacity,
    counts_as_moved_in,
    fixed_placements,
    home_use,
    move_minutes,
    remaining_equipment_need,
    return_minutes,
)
from smartcampus.rules.base import RuleId
from smartcampus.rules.variables import DecisionVars, build_variables

ROOT = Path(__file__).parents[2] / "scenarios"
SMALL = sorted((ROOT / "frozen").glob("small-*.json"))
MEDIUM = sorted((ROOT / "frozen").glob("medium-*.json"))


def post_r5_old(ctx: DecisionVars) -> None:
    model, problem = ctx.model, ctx.problem
    lit = ctx.rule_lit[RuleId.R5]
    intervals = []
    for key, units in ctx.units.items():
        activity_id, pool_id = key
        moved, start = ctx.moved[key], ctx.move_start[key]
        pool = problem.campus.pool(pool_id)
        length = move_minutes(pool, units)
        end = model.new_int_var(0, WEEK_END_MIN + move_minutes(pool, pool.units), "move_end")
        model.add(end == start + length)
        model.add(start >= problem.plan_time_min).only_enforce_if([moved, lit])
        model.add(end <= WEEK_END_MIN).only_enforce_if([moved, lit])
        for option in ctx.options[activity_id]:
            if option.var is not None:
                model.add(end <= option.start).only_enforce_if([option.var, moved, lit])
        intervals.append(
            model.new_optional_interval_var(
                start, length, end, ctx.and_literal(moved, lit), f"move_{activity_id}_{pool_id}"
            )
        )
    model.add_cumulative(intervals, [1] * len(intervals), problem.staff_available)


def post_r4_old(ctx: DecisionVars) -> None:
    lit = ctx.rule_lit[RuleId.R4]
    pools = ctx.problem.campus.pools
    for option in ctx.all_options():
        if r4.has_wrong_type(option):
            ctx.forbid(option, RuleId.R4)
        for eq_type, missing in remaining_equipment_need(ctx.problem, option).items():
            if option.var is None:
                ctx.forbid(option, RuleId.R4)
                continue
            moved_in = [
                ctx.units[(option.activity.id, p.id)]
                for p in pools
                if counts_as_moved_in(p, eq_type, option.room.id)
            ]
            if moved_in:
                ctx.model.add(cp_model.LinearExpr.sum(moved_in) >= missing).only_enforce_if(
                    [option.var, lit]
                )
            else:
                ctx.forbid(option, RuleId.R4)
    for (_, pool_id), units in ctx.units.items():
        if not ctx.problem.campus.pool(pool_id).movable:
            ctx.model.add(units == 0).only_enforce_if(lit)
    model, problem = ctx.model, ctx.problem
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
            placed = [o.var for o in ctx.options[key[0]] if o.var is not None]
            model.add_bool_or([*placed, moved.negated()]).only_enforce_if(lit)
            back = model.new_int_var(0, horizon, f"back_{key[0]}_{key[1]}")
            for option in ctx.options[key[0]]:
                if option.var is not None:
                    model.add(back == option.end + return_minutes(pool, units)).only_enforce_if(
                        [option.var, moved, lit]
                    )
            until = model.new_int_var(0, horizon, f"until_{key[0]}_{key[1]}")
            model.add_max_equality(until, [start, back])
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


def choose(ctx: DecisionVars, needs_moves: bool) -> dict[str, Placement]:
    """One allowed placement per movable class, no room used twice at once. Prefer rooms that
    lack the class's equipment (so it needs moves) or that already have it."""
    problem = ctx.problem
    taken = {(f.room.id, slot) for f in fixed_placements(problem) for slot in f.slots}
    chosen: dict[str, Placement] = {}
    for activity_id, options in ctx.options.items():
        usable = [o for o in options if o.var is not None and not r4.has_wrong_type(o)]
        free = [o for o in usable if not any((o.room.id, s) in taken for s in o.slots)]
        wanted = [o for o in free if bool(remaining_equipment_need(problem, o)) == needs_moves]
        for pick in (wanted or free or usable)[:1]:
            chosen[activity_id] = pick
            taken.update((pick.room.id, slot) for slot in pick.slots)
    return chosen


def build_plans(ctx: DecisionVars) -> dict[str, Plan]:
    """A plan that needs no moves, and variants of a plan whose classes all need moves."""
    problem = ctx.problem
    home = choose(ctx, needs_moves=False)
    chosen = choose(ctx, needs_moves=True)
    fed: dict[tuple[str, str], EquipmentMove] = {}
    for activity_id, placed in chosen.items():
        for eq_type, missing in remaining_equipment_need(problem, placed).items():
            for pool in problem.campus.pools:
                key = (activity_id, pool.id)
                if (
                    key in fed
                    or not pool.movable
                    or not counts_as_moved_in(pool, eq_type, placed.room.id)
                ):
                    continue
                units = min(missing, pool.units)
                length = move_minutes(pool, units)
                start = max(problem.plan_time_min, placed.start - length)
                fed[key] = EquipmentMove(
                    pool_id=pool.id,
                    activity_id=activity_id,
                    units=units,
                    start_min=start,
                    end_min=start + length,
                )
                break

    def plan(moves: list[EquipmentMove], where: dict[str, Placement] = chosen) -> Plan:
        return Plan(
            based_on_version=0,
            assignments=tuple(
                Assignment(activity_id=a, room_id=p.room.id, start_min=p.start)
                for a, p in where.items()
            ),
            cancelled=frozenset(),
            moves=tuple(moves),
        )

    def shifted(move: EquipmentMove, by: int) -> EquipmentMove:
        start = min(max(move.start_min + by, 0), WEEK_END_MIN - 1)
        return move.model_copy(
            update={"start_min": start, "end_min": start + move.end_min - move.start_min}
        )

    def overrun(move: EquipmentMove) -> EquipmentMove:
        class_start = chosen[move.activity_id].start
        start = class_start + 30 - (move.end_min - move.start_min)
        return move.model_copy(update={"start_min": start, "end_min": class_start + 30})

    moves = list(fed.values())
    one_short = [m.model_copy(update={"units": max(1, m.units - 1)}) for m in moves]
    unneeded: list[EquipmentMove] = []
    spare = next(
        (
            (a, pool)
            for a in chosen
            for pool in problem.campus.pools
            if pool.movable and (a, pool.id) not in fed
        ),
        None,
    )
    if spare is not None:
        a, pool = spare
        length = move_minutes(pool, 1)
        start = max(problem.plan_time_min, chosen[a].start - length)
        unneeded = [
            EquipmentMove(
                pool_id=pool.id, activity_id=a, units=1, start_min=start, end_min=start + length
            )
        ]
    return {
        "home": plan([], home),
        "none": plan([]),
        "fed": plan(moves),
        "late": plan([shifted(m, 30) for m in moves]),
        "short": plan(
            [
                m.model_copy(
                    update={
                        "end_min": m.start_min
                        + move_minutes(problem.campus.pool(m.pool_id), m.units)
                    }
                )
                for m in one_short
            ]
        ),
        "crowd": plan([shifted(m, problem.plan_time_min - m.start_min) for m in moves]),
        "unneeded": plan([*moves, *unneeded]),
        # An unneeded move that ends 30 minutes into its class: R5 must reject it.
        "overrun": plan([*moves, *(overrun(m) for m in unneeded)]),
    }


def pinned_feasible(ctx: DecisionVars, plan: Plan) -> bool:
    """Fix every decision variable to the plan: does the posted model still have a solution?"""
    chosen = {(a.activity_id, a.room_id, a.start_min) for a in plan.assignments}
    moves = {(m.activity_id, m.pool_id): m for m in plan.moves}
    ctx.model.clear_hints()  # type: ignore[no-untyped-call]
    for activity_id, options in ctx.options.items():
        for o in options:
            if o.var is not None:
                ctx.model.add_hint(o.var, int((activity_id, o.room.id, o.start) in chosen))
    for var in ctx.cancelled.values():
        ctx.model.add_hint(var, 0)
    for key, units_var in ctx.units.items():
        move = moves.get(key)
        ctx.model.add_hint(units_var, move.units if move else 0)
        ctx.model.add_hint(ctx.moved[key], int(move is not None))
        ctx.model.add_hint(ctx.move_start[key], move.start_min if move else 0)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.max_time_in_seconds = 60
    solver.parameters.fix_variables_to_their_hinted_value = True
    status = solver.solve(ctx.model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE), status
    return status != cp_model.INFEASIBLE


def model(problem: RecoveryProblem, *posts: object) -> DecisionVars:
    ctx = build_variables(problem)
    for post, rule_id in posts:  # type: ignore[misc]
        post(ctx)
        ctx.model.add(ctx.rule_lit[rule_id] == 1)
    return ctx


@pytest.mark.parametrize("path", [*SMALL, *MEDIUM], ids=lambda p: p.stem)
def test_new_and_old_encoding_accept_and_reject_the_same_plans(path: Path) -> None:
    problem = load_scenario(path)
    new = model(problem, (r4.post, RuleId.R4), (r5.post, RuleId.R5))
    old = model(problem, (post_r4_old, RuleId.R4), (post_r5_old, RuleId.R5))
    verdicts = {}
    for name, plan in build_plans(new).items():
        oracle = not (r4.check(problem, plan) or r5.check(problem, plan))
        verdicts[name] = (oracle, pinned_feasible(new, plan), pinned_feasible(old, plan))
    for name, (oracle, new_ok, old_ok) in verdicts.items():
        assert new_ok == old_ok == oracle, f"{name}: validator {oracle}, new {new_ok}, old {old_ok}"
    assert any(not oracle for oracle, _, _ in verdicts.values()), "no plan was rejected"
    assert any(oracle for oracle, _, _ in verdicts.values()), "no plan was accepted"
