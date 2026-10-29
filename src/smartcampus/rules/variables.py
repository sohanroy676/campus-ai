"""CP-SAT decision variables shared by every rule's `post` (see docs/model-spec.md section 2).

Rule constraints are only enforced when the rule's assumption literal is true, so an infeasible
core names the conflicting rules.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from ortools.sat.python import cp_model

from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules._shared import (
    WEEK_END_MIN,
    Placement,
    fixed_placements,
    valid_starts,
)
from smartcampus.rules.base import RuleId


@dataclass
class DecisionVars:
    problem: RecoveryProblem
    model: cp_model.CpModel
    # Per activity: every candidate placement (var set) or the single fixed one (var None).
    options: dict[str, list[Placement]]
    cancelled: dict[str, cp_model.IntVar]
    # Keyed by (activity id, pool id) for every affected activity and every pool.
    units: dict[tuple[str, str], cp_model.IntVar]
    moved: dict[tuple[str, str], cp_model.IntVar]
    move_start: dict[tuple[str, str], cp_model.IntVar]
    rule_lit: dict[RuleId, cp_model.IntVar]

    def all_options(self) -> Iterator[Placement]:
        for placements in self.options.values():
            yield from placements

    def forbid(self, option: Placement, rule: RuleId) -> None:
        """Under `rule`, this placement may not happen."""
        lit = self.rule_lit[rule]
        if option.var is None:
            self.model.add_bool_or([lit.negated()])
        else:
            self.model.add(option.var == 0).only_enforce_if(lit)

    def forbid_together(self, first: Placement, second: Placement, rule: RuleId) -> None:
        """Under `rule`, these two placements may not both happen."""
        if first.var is None:
            self.forbid(second, rule)
        elif second.var is None:
            self.forbid(first, rule)
        else:
            self.model.add_bool_or([first.var.negated(), second.var.negated()]).only_enforce_if(
                self.rule_lit[rule]
            )

    def at_most_one(self, options: list[Placement], rule: RuleId) -> None:
        """Under `rule`, at most one of these placements may happen."""
        fixed = sum(o.var is None for o in options)
        chosen = [o for o in options if o.var is not None]
        if fixed > 1:
            self.model.add_bool_or([self.rule_lit[rule].negated()])
        elif fixed == 1:
            for option in chosen:
                self.forbid(option, rule)
        elif len(chosen) > 1:
            self.model.add_at_most_one(
                [o.var for o in chosen if o.var is not None]
            ).only_enforce_if(self.rule_lit[rule])

    def and_literal(self, first: cp_model.IntVar, second: cp_model.IntVar) -> cp_model.IntVar:
        out = self.model.new_bool_var("")
        self.model.add_bool_and([first, second]).only_enforce_if(out)
        self.model.add_bool_or([first.negated(), second.negated()]).only_enforce_if(out.negated())
        return out


def build_variables(problem: RecoveryProblem) -> DecisionVars:
    """Create the variables for the affected activities; unaffected ones stay constants."""
    model = cp_model.CpModel()
    options: dict[str, list[Placement]] = {}
    for fixed in fixed_placements(problem):
        options[fixed.activity.id] = [fixed]
    cancelled: dict[str, cp_model.IntVar] = {}
    units: dict[tuple[str, str], cp_model.IntVar] = {}
    moved: dict[tuple[str, str], cp_model.IntVar] = {}
    move_start: dict[tuple[str, str], cp_model.IntVar] = {}
    for activity in problem.activities:
        if activity.id not in problem.movable_activity_ids:
            continue
        options[activity.id] = [
            Placement(
                activity, room, start, model.new_bool_var(f"x_{activity.id}_{room.id}_{start}")
            )
            for room in problem.campus.rooms
            for start in valid_starts(problem, activity)
        ]
        cancelled[activity.id] = model.new_bool_var(f"cancelled_{activity.id}")
        for pool in problem.campus.pools:
            key = (activity.id, pool.id)
            suffix = f"{activity.id}_{pool.id}"
            units[key] = model.new_int_var(0, pool.units, f"units_{suffix}")
            moved[key] = model.new_bool_var(f"moved_{suffix}")
            move_start[key] = model.new_int_var(0, WEEK_END_MIN, f"move_start_{suffix}")
            model.add(units[key] >= 1).only_enforce_if(moved[key])
            model.add(units[key] == 0).only_enforce_if(moved[key].negated())
    rule_lit = {rule: model.new_bool_var(f"rule_{rule}") for rule in RuleId}
    return DecisionVars(problem, model, options, cancelled, units, moved, move_start, rule_lit)
