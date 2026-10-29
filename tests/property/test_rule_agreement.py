"""The validator check and the CP-SAT encoding of each rule must accept exactly the same plans."""

import pytest
from cp_helpers import allows, conflicting_rules
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from strategies import REPRESENTABLE_MODES, plans, problems

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.registry import ALL_RULES, HardRule
from smartcampus.rules.validator import validate


@pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.id.value)
@settings(max_examples=60)
@given(data=st.data())
def test_check_and_encoding_agree_on_every_representable_plan(
    rule: HardRule, data: st.DataObject
) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, modes=REPRESENTABLE_MODES))
    assert (rule.check(problem, plan) == []) == allows(problem, plan, [rule]), rule.check(
        problem, plan
    )


@settings(max_examples=100)
@given(data=st.data())
def test_validator_and_full_model_agree_even_on_malformed_plans(data: st.DataObject) -> None:
    """Plans the variables cannot express (unknown ids, off-grid times) must fail a check."""
    problem = data.draw(problems())
    plan = data.draw(plans(problem, modes=REPRESENTABLE_MODES, wild=True))
    violations = validate(problem, plan)
    assert (violations == []) == allows(problem, plan), violations


@settings(max_examples=60)
@given(problem=problems(all_movable=True))
def test_the_full_model_can_always_cancel(problem: RecoveryProblem) -> None:
    cancel_all = Plan(based_on_version=0, cancelled=problem.movable_activity_ids)
    assert allows(problem, cancel_all)


@settings(max_examples=60)
@given(data=st.data())
def test_infeasible_core_names_at_least_one_really_violated_rule(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, modes=REPRESENTABLE_MODES))
    violated = {v.rule for v in validate(problem, plan)}
    assume(violated)
    core = conflicting_rules(problem, plan)
    assert core, "an infeasible plan must produce a non-empty core"
    assert core & violated
