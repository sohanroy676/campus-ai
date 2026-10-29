from hypothesis import given
from hypothesis import strategies as st
from strategies import REPRESENTABLE_MODES, plans, problems

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.registry import ALL_RULES
from smartcampus.rules.validator import validate


@given(problems(all_movable=True))
def test_cancelling_everything_is_always_valid(problem: RecoveryProblem) -> None:
    """The model can always cancel, so cancelling every affected activity breaks nothing."""
    assert validate(problem, Plan(based_on_version=0, cancelled=problem.movable_activity_ids)) == []


@given(st.data())
def test_no_plan_makes_a_rule_raise_and_results_are_repeatable(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, modes=REPRESENTABLE_MODES, wild=True))
    assert validate(problem, plan) == validate(problem, plan)


@given(st.data())
def test_validate_is_the_union_of_the_rule_checks(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, modes=REPRESENTABLE_MODES, wild=True))
    by_rule = [v for rule in ALL_RULES for v in rule.check(problem, plan)]
    assert validate(problem, plan) == by_rule
    assert all(v.rule == rule.id for rule in ALL_RULES for v in rule.check(problem, plan))
