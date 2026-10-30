"""R6 grouped encoding against the old pairwise encoding on the generated scenarios.

The old encoding forbade every pair of options with a shared person that are back-to-back between
far buildings. The new one groups options by (person, time, building). For each scenario this
builds a handful of plans (clean, back-to-back far, overlapping, back-to-back near), pins each in
both models and asks whether the model still has a solution. The two must agree with each other
and with the validator's `check`.

The old encoding is rebuilt here as a reference. Over all option pairs it takes minutes on a
medium scenario, so the reference only pairs the options some test plan picks (plus fixed ones).
That gives the same answer for these plans: every other option is pinned to 0 and so satisfies
any pair clause. The far-apart rule only exists on campuses with a walk over the limit, so each
scenario is checked for that and must reject its back-to-back far plan.
"""

from collections import defaultdict
from collections.abc import Iterable
from itertools import combinations
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from smartcampus.domain.plan import Assignment, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.generator.scenario import load_scenario
from smartcampus.rules import r6_people_conflict as r6
from smartcampus.rules._shared import MAX_BACK_TO_BACK_TRAVEL_MIN, Placement, fixed_placements
from smartcampus.rules.base import RuleId
from smartcampus.rules.variables import DecisionVars, build_variables

ROOT = Path(__file__).parents[2] / "scenarios"
SMALL = sorted((ROOT / "frozen").glob("small-*.json"))
MEDIUM = sorted((ROOT / "frozen").glob("medium-*.json"))


def post_pairwise(ctx: DecisionVars, kept: set[int]) -> None:
    """The R6 encoding before the grouping change, with the pair loop limited to `kept` options."""
    people: dict[str, list[Placement]] = defaultdict(list)
    for option in ctx.all_options():
        a = option.activity
        for person in (f"cohort:{a.cohort_id}", *(f"faculty:{f}" for f in a.faculty_ids)):
            people[person].append(option)
    for options in people.values():
        by_slot: dict[int, list[Placement]] = defaultdict(list)
        for option in options:
            for slot in option.slots:
                by_slot[slot].append(option)
        for group in by_slot.values():
            ctx.at_most_one(group, RuleId.R6)
    pool = [o for o in ctx.all_options() if o.var is None or o.var.index in kept]
    for first, second in combinations(pool, 2):
        if r6.shares_person(first, second) and r6.is_too_far(ctx.problem, first, second):
            ctx.forbid_together(first, second, RuleId.R6)


def persons(placement: Placement) -> list[str]:
    a = placement.activity
    return [f"cohort:{a.cohort_id}", *(f"faculty:{f}" for f in a.faculty_ids)]


def conflicts(
    problem: RecoveryProblem, option: Placement, busy: dict[str, list[Placement]]
) -> bool:
    """True if `option` overlaps, or is back-to-back far from, a placement of one of its people."""
    return any(
        (other.start < option.end and option.start < other.end)
        or r6.is_too_far(problem, option, other)
        for person in persons(option)
        for other in busy[person]
    )


def build_plans(ctx: DecisionVars) -> dict[str, Plan]:
    """Four plans over the movable activities; which ones R6 accepts is left to `check`."""
    movable = [aid for aid, opts in ctx.options.items() if any(o.var is not None for o in opts)]
    fixed = fixed_placements(ctx.problem)  # classes that are not movable keep their slot

    def clean() -> dict[str, Placement]:
        busy: dict[str, list[Placement]] = defaultdict(list)
        for o in fixed:
            for person in persons(o):
                busy[person].append(o)
        chosen: dict[str, Placement] = {}
        for aid in movable:
            options = [o for o in ctx.options[aid] if o.var is not None]
            pick = next((o for o in options if not conflicts(ctx.problem, o, busy)), options[0])
            chosen[aid] = pick
            for person in persons(pick):
                busy[person].append(pick)
        return chosen

    base = clean()

    def forced(kind: str) -> dict[str, Placement]:
        """`base` with one activity moved to an option that touches a chosen one of its people."""
        by_time: dict[tuple[str, int], list[Placement]] = defaultdict(list)
        for pick in [*base.values(), *fixed]:
            for person in persons(pick):
                by_time[person, pick.start if kind == "overlap" else pick.end].append(pick)
        for aid in movable:
            for q in ctx.options[aid]:
                if q.var is None:
                    continue
                for person in persons(q):
                    for p in by_time.get((person, q.start), []):
                        if p.activity.id == aid:
                            continue
                        far = r6.is_too_far(ctx.problem, p, q)
                        if kind == "overlap" or far == (kind == "far"):
                            return {**base, aid: q}
        return base

    chosen_by_plan = {
        "clean": base,
        "far": forced("far"),
        "overlap": forced("overlap"),
        "near": forced("near"),
    }
    return {
        name: Plan(
            based_on_version=0,
            assignments=tuple(
                Assignment(activity_id=aid, room_id=o.room.id, start_min=o.start)
                for aid, o in chosen.items()
            ),
            cancelled=frozenset(),
            moves=(),
        )
        for name, chosen in chosen_by_plan.items()
    }


def pinned_feasible(ctx: DecisionVars, plan: Plan) -> bool:
    """Pin every option to the plan: does R6, the only posted rule, still have a solution?"""
    chosen = {(a.activity_id, a.room_id, a.start_min) for a in plan.assignments}
    assumptions = [
        o.var if (aid, o.room.id, o.start) in chosen else o.var.negated()
        for aid, options in ctx.options.items()
        for o in options
        if o.var is not None
    ]
    ctx.model.clear_assumptions()
    ctx.model.add_assumptions(assumptions)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.max_time_in_seconds = 60
    status = solver.solve(ctx.model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE), status
    return status != cp_model.INFEASIBLE


def kept_options(plans: Iterable[Plan], ctx: DecisionVars) -> set[int]:
    chosen = {(a.activity_id, a.room_id, a.start_min) for p in plans for a in p.assignments}
    return {
        o.var.index
        for aid, options in ctx.options.items()
        for o in options
        if o.var is not None and (aid, o.room.id, o.start) in chosen
    }


def compare(problem: RecoveryProblem) -> dict[str, tuple[bool, bool, bool]]:
    """For each plan: (validator accepts, new encoding accepts, old encoding accepts)."""
    new_ctx = build_variables(problem)
    r6.post(new_ctx)
    new_ctx.model.add(new_ctx.rule_lit[RuleId.R6] == 1)
    plans = build_plans(new_ctx)
    old_ctx = build_variables(problem)
    post_pairwise(old_ctx, kept_options(plans.values(), old_ctx))
    old_ctx.model.add(old_ctx.rule_lit[RuleId.R6] == 1)
    return {
        name: (
            not r6.check(problem, plan),
            pinned_feasible(new_ctx, plan),
            pinned_feasible(old_ctx, plan),
        )
        for name, plan in plans.items()
    }


@pytest.mark.parametrize("path", [*SMALL, *MEDIUM], ids=lambda p: p.stem)
def test_new_and_old_encoding_accept_and_reject_the_same_plans(path: Path) -> None:
    verdicts = compare(load_scenario(path))
    for name, (validator, new, old) in verdicts.items():
        assert new == old == validator, f"{name}: validator {validator}, new {new}, old {old}"
    assert any(not validator for validator, _, _ in verdicts.values()), "no plan was rejected"
    assert any(validator for validator, _, _ in verdicts.values()), "no plan was accepted"
    campus = load_scenario(path).campus
    ids = [b.id for b in campus.buildings]
    if any(
        campus.travel_minutes(a, b) > MAX_BACK_TO_BACK_TRAVEL_MIN for a, b in combinations(ids, 2)
    ):
        assert not verdicts["far"][0], "no back-to-back far plan could be built"
