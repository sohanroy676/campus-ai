from builders import asg, at, evolve, make_activity, make_plan, make_problem
from cp_helpers import conflicting_rules, solver
from ortools.sat.python import cp_model

from smartcampus.domain.entities import Cohort
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.rules.base import RuleId
from smartcampus.rules.registry import RULES_BY_ID
from smartcampus.rules.variables import build_variables

TUE_10 = at(1, 10)


def two_activity_problem() -> RecoveryProblem:
    return make_problem(
        activities=(make_activity(), make_activity(id="fixed", cohort_id="c2", room_id="A2")),
    )


def test_only_affected_activities_get_variables() -> None:
    ctx = build_variables(two_activity_problem())
    assert set(ctx.cancelled) == {"act1"}
    assert ctx.options["fixed"][0].var is None
    assert all(o.var is not None for o in ctx.options["act1"])
    assert (
        set(ctx.units)
        == set(ctx.moved)
        == set(ctx.move_start)
        == {("act1", "gpu"), ("act1", "rack")}
    )
    assert set(ctx.rule_lit) == set(RuleId)


def test_candidates_are_every_room_and_every_start_that_fits_the_window() -> None:
    problem = evolve(make_problem(), window=Interval(start=at(1, 9), end=at(1, 11)))
    ctx = build_variables(problem)
    starts = {o.start for o in ctx.options["act1"]}
    assert starts == {at(1, 9), at(1, 9, 30), at(1, 10)}  # two slots long, so 10:30 would overrun
    assert {o.room.id for o in ctx.options["act1"]} == {"A1", "A2", "B1"}


def test_unit_variables_are_bounded_by_the_pool_and_linked_to_moved() -> None:
    ctx = build_variables(make_problem())
    ctx.model.add(ctx.units[("act1", "gpu")] == 5)  # the pool only has 4
    assert solver().solve(ctx.model) == cp_model.INFEASIBLE
    ctx = build_variables(make_problem())
    ctx.model.add(ctx.units[("act1", "gpu")] == 3)
    assert solver().solve(ctx.model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    # moved is exactly "units > 0"
    ctx = build_variables(make_problem())
    ctx.model.add(ctx.moved[("act1", "gpu")] == 0)
    ctx.model.add(ctx.units[("act1", "gpu")] == 1)
    assert solver().solve(ctx.model) == cp_model.INFEASIBLE


def test_constraints_bind_only_while_their_rule_literal_is_true() -> None:
    problem = two_activity_problem()
    ctx = build_variables(problem)
    first, second = ctx.options["act1"][0], ctx.options["fixed"][0]
    ctx.at_most_one([second, second], RuleId.R2)  # two constants: always broken
    ctx.model.add(ctx.rule_lit[RuleId.R2] == 1)
    assert solver().solve(ctx.model) == cp_model.INFEASIBLE
    ctx = build_variables(problem)
    ctx.at_most_one([second, second], RuleId.R2)
    ctx.forbid(first, RuleId.R2)
    ctx.model.add(ctx.rule_lit[RuleId.R2] == 0)
    assert solver().solve(ctx.model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_forbid_together_blocks_only_the_pair() -> None:
    ctx = build_variables(
        make_problem(
            activities=(make_activity(), make_activity(id="act2")),
            movable_activity_ids=frozenset({"act1", "act2"}),
        )
    )
    one, other = ctx.options["act1"][0], ctx.options["act2"][0]
    assert one.var is not None and other.var is not None
    ctx.forbid_together(one, other, RuleId.R6)
    ctx.model.add(ctx.rule_lit[RuleId.R6] == 1)
    ctx.model.add(one.var == 1)
    ctx.model.add(other.var == 1)
    assert solver().solve(ctx.model) == cp_model.INFEASIBLE


def test_infeasible_core_names_the_conflicting_rule() -> None:
    problem = evolve(
        make_problem(), cohorts=(Cohort(id="c1", size=45), Cohort(id="c2", size=20))
    )  # 45 students do not fit the 30 seats of A1; everything else is fine
    plan = make_plan(asg("act1", "A1", TUE_10))
    assert [v.rule for v in RULES_BY_ID[RuleId.R3].check(problem, plan)] == [RuleId.R3]
    assert conflicting_rules(problem, plan) == {RuleId.R3}


def test_a_sound_plan_has_an_empty_core() -> None:
    assert conflicting_rules(make_problem(), make_plan(asg("act1", "A1", TUE_10))) == set()
