"""CP-SAT decision variables shared by every rule's `post` (see docs/model-spec.md section 2).

Rule constraints are only enforced when the rule's assumption literal is true, so an infeasible
core names the conflicting rules.
"""

from collections import defaultdict
from collections.abc import Hashable, Iterator, Sequence
from dataclasses import dataclass, field

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
    _groups: dict[Hashable, cp_model.IntVar | None] = field(default_factory=dict, repr=False)
    _building_starts: dict[str, dict[tuple[int, str], cp_model.IntVar | None]] = field(
        default_factory=dict, repr=False
    )
    _starts: dict[str, dict[int, cp_model.IntVar | None]] = field(default_factory=dict, repr=False)
    _start_bounds: dict[str, tuple[cp_model.IntVar, cp_model.IntVar]] = field(
        default_factory=dict, repr=False
    )

    def any_happens(self, key: Hashable, group: Sequence[Placement]) -> cp_model.IntVar | None:
        """A literal that is true whenever some placement in `group` happens.

        It may also be true when none does, so use it only where "true" restricts the plan. None
        when a member is fixed (it always happens). Asking again for the same `key` returns the
        same literal, so rules that group the same placements share one set of implications.
        """
        if key in self._groups:
            return self._groups[key]
        literal: cp_model.IntVar | None
        variables = [o.var for o in group if o.var is not None]
        if len(variables) < len(group):
            literal = None
        elif len(variables) == 1:
            literal = variables[0]
        else:
            literal = self.model.new_bool_var("")
            for var in variables:
                self.model.add_implication(var, literal)
        self._groups[key] = literal
        return literal

    def building_start_literals(
        self, activity_id: str
    ) -> dict[tuple[int, str], cp_model.IntVar | None]:
        """For each (start, building) of the activity's placements, "one of them happens".

        Every placement is tied to exactly one of these literals, and all coarser groups (by start
        time, by end time) are built from them, so a placement carries a single implication.
        """
        cached = self._building_starts.get(activity_id)
        if cached is None:
            groups: dict[tuple[int, str], list[Placement]] = defaultdict(list)
            for option in self.options[activity_id]:
                groups[option.start, option.room.building_id].append(option)
            cached = {
                (start, building): self.any_happens(
                    ("start_building", activity_id, start, building), group
                )
                for (start, building), group in groups.items()
            }
            self._building_starts[activity_id] = cached
        return cached

    def start_literals(self, activity_id: str) -> dict[int, cp_model.IntVar | None]:
        """For each start time of the activity's placements, "one with this start happens"."""
        cached = self._starts.get(activity_id)
        if cached is None:
            by_start: dict[int, list[cp_model.IntVar | None]] = defaultdict(list)
            for (start, _), literal in self.building_start_literals(activity_id).items():
                by_start[start].append(literal)
            cached = {}
            for start, literals in by_start.items():
                if any(literal is None for literal in literals):
                    cached[start] = None
                elif len(literals) == 1:
                    cached[start] = literals[0]
                else:
                    joined = self.model.new_bool_var("")
                    for literal in literals:
                        assert literal is not None
                        self.model.add_implication(literal, joined)
                    cached[start] = joined
            self._starts[activity_id] = cached
        return cached

    def start_bounds(self, activity_id: str) -> tuple[cp_model.IntVar, cp_model.IntVar]:
        """Variables (earliest, latest) with earliest <= every chosen start <= latest.

        Both are free outside those bounds, so a rule that needs "before every chosen start" or
        "equal to the only chosen start" can state it once per class instead of once per start time.
        Where no placement happens they are unconstrained, which is how the rules already treat it.
        """
        cached = self._start_bounds.get(activity_id)
        if cached is None:
            earliest = self.model.new_int_var(0, WEEK_END_MIN, f"earliest_{activity_id}")
            latest = self.model.new_int_var(0, WEEK_END_MIN, f"latest_{activity_id}")
            for start, here in self.start_literals(activity_id).items():
                if here is not None:
                    self.model.add(earliest <= start).only_enforce_if(here)
                    self.model.add(latest >= start).only_enforce_if(here)
            cached = (earliest, latest)
            self._start_bounds[activity_id] = cached
        return cached

    def end_literals(self, activity_id: str) -> dict[int, cp_model.IntVar | None]:
        """For each end time of the activity's placements, "one with this end happens".

        A class has one duration, so these are the start literals under a shifted time.
        """
        duration = self.problem.activity(activity_id).duration_min
        return {t + duration: lit for t, lit in self.start_literals(activity_id).items()}

    def placed_literal(self, activity_id: str) -> cp_model.IntVar | None:
        """A literal that, when true, forces some placement of the activity to happen.

        The other direction from `any_happens`: use it where "true" is a requirement. It may be
        false even when a placement happens. None when a placement is fixed (so always placed).
        """
        key = ("placed", activity_id)
        if key not in self._groups:
            variables = [o.var for o in self.options[activity_id] if o.var is not None]
            literal: cp_model.IntVar | None = None
            if len(variables) == len(self.options[activity_id]):
                literal = self.model.new_bool_var("")
                self.model.add_bool_or(variables).only_enforce_if(literal)
            self._groups[key] = literal
        return self._groups[key]

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
