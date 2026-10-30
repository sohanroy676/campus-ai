"""R6 people_conflict: nobody is in two places at once, and back-to-back travel is short enough.

Two classes with a common cohort or faculty member may not overlap. If one ends exactly when the
other starts, their buildings must be at most 10 minutes apart.
"""

from collections import defaultdict

from ortools.sat.python import cp_model

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    MAX_BACK_TO_BACK_TRAVEL_MIN,
    Placement,
    intervals_overlap,
    placements,
)
from smartcampus.rules.base import RuleId, Violation
from smartcampus.rules.variables import DecisionVars


def shares_person(first: Placement, second: Placement) -> bool:
    a, b = first.activity, second.activity
    return a.cohort_id == b.cohort_id or bool(set(a.faculty_ids) & set(b.faculty_ids))


def is_too_far(problem: RecoveryProblem, first: Placement, second: Placement) -> bool:
    """Back-to-back in either order with a walk longer than the allowed gap."""
    back_to_back = first.end == second.start or second.end == first.start
    walk = problem.campus.travel_minutes(first.room.building_id, second.room.building_id)
    return back_to_back and walk > MAX_BACK_TO_BACK_TRAVEL_MIN


def check(problem: RecoveryProblem, plan: Plan) -> list[Violation]:
    out: list[Violation] = []
    found = placements(problem, plan)
    for i, p in enumerate(found):
        for q in found[i + 1 :]:
            if not shares_person(p, q):
                continue
            ids = tuple(sorted((p.activity.id, q.activity.id)))
            rooms = tuple(sorted({p.room.id, q.room.id}))
            if intervals_overlap(p.start, p.end, q.start, q.end):
                out.append(
                    Violation(
                        RuleId.R6, f"{ids[0]} and {ids[1]} share a person and overlap", ids, rooms
                    )
                )
            elif is_too_far(problem, p, q):
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


def post(ctx: DecisionVars) -> None:
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
        _forbid_far_back_to_back(ctx, options)


def _forbid_far_back_to_back(ctx: DecisionVars, options: list[Placement]) -> None:
    """One person: nothing ends in building b at time t while something starts in a far b' at t.

    Same pairs as checking every two options with `is_too_far`, but grouped by (time, building) so
    the model grows with the number of time boundaries, not with the number of option pairs.
    """
    ending: dict[int, dict[str, list[Placement]]] = defaultdict(lambda: defaultdict(list))
    starting: dict[int, dict[str, list[Placement]]] = defaultdict(lambda: defaultdict(list))
    for option in options:
        ending[option.end][option.room.building_id].append(option)
        starting[option.start][option.room.building_id].append(option)
    campus = ctx.problem.campus
    for time, ends_by_building in ending.items():
        starts_by_building = starting.get(time)
        if starts_by_building is None:
            continue
        made: dict[tuple[str, str], cp_model.IntVar | None] = {}  # literal per group, made once
        for end_building, ends in ends_by_building.items():
            for start_building, starts in starts_by_building.items():
                if (
                    campus.travel_minutes(end_building, start_building)
                    <= MAX_BACK_TO_BACK_TRAVEL_MIN
                ):
                    continue
                for side, building, group in (
                    ("end", end_building, ends),
                    ("start", start_building, starts),
                ):
                    if (side, building) not in made:
                        made[side, building] = _any_happens(ctx, group)
                _forbid_together(ctx, made["end", end_building], made["start", start_building])


def _forbid_together(
    ctx: DecisionVars, first: cp_model.IntVar | None, second: cp_model.IntVar | None
) -> None:
    """Under R6, not both literals true; None stands for a literal that is always true."""
    lit = ctx.rule_lit[RuleId.R6]
    if first is None and second is None:
        ctx.model.add_bool_or([lit.negated()])
    elif first is None or second is None:
        (only,) = [v for v in (first, second) if v is not None]
        ctx.model.add(only == 0).only_enforce_if(lit)
    else:
        ctx.model.add_bool_or([first.negated(), second.negated()]).only_enforce_if(lit)


def _any_happens(ctx: DecisionVars, group: list[Placement]) -> cp_model.IntVar | None:
    """A literal true whenever some option in `group` happens; None if one is fixed (so always)."""
    if any(option.var is None for option in group):
        return None
    variables = [option.var for option in group if option.var is not None]
    if len(variables) == 1:
        return variables[0]
    indicator = ctx.model.new_bool_var("")
    for var in variables:
        ctx.model.add_implication(var, indicator)
    return indicator
