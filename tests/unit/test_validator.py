import pytest
from builders import asg, at, evolve, make_activity, make_plan, make_problem, rule_ids

from smartcampus.domain.entities import Cohort, SafetyHold
from smartcampus.domain.time import Interval
from smartcampus.rules.base import RuleId
from smartcampus.rules.registry import ALL_RULES, RULES_BY_ID
from smartcampus.rules.validator import PlanInvalidError, assert_valid, validate

TUE_10 = at(1, 10)


def test_registry_lists_the_eight_rules_in_order() -> None:
    assert [r.id for r in ALL_RULES] == list(RuleId)
    assert [r.id.value for r in ALL_RULES] == [f"R{i}" for i in range(1, 9)]
    assert set(RULES_BY_ID) == set(RuleId)


def test_a_sound_plan_has_no_violations() -> None:
    problem = make_problem()
    for plan in (make_plan(asg("act1", "A1", TUE_10)), make_plan(cancelled=("act1",))):
        assert validate(problem, plan) == []
        assert_valid(problem, plan)


def test_empty_plan_breaks_only_r1() -> None:
    assert rule_ids(validate(make_problem(), make_plan())) == [RuleId.R1]


def test_one_placement_can_break_several_rules_at_once() -> None:
    # 40-seat B1 has steps and is on hold; the 45-strong step-free cohort also needs a lab.
    problem = evolve(
        make_problem(activities=(make_activity(allowed_room_types=frozenset({"lab"})),)),
        cohorts=(Cohort(id="c1", size=45, step_free_required=True), Cohort(id="c2", size=20)),
        holds=(
            SafetyHold(
                target_kind="room", target_id="B1", interval=Interval(start=TUE_10, end=at(1, 11))
            ),
        ),
    )
    found = rule_ids(validate(problem, make_plan(asg("act1", "B1", TUE_10))))
    assert found == [RuleId.R2, RuleId.R3, RuleId.R4, RuleId.R7, RuleId.R8]


def test_assert_valid_raises_with_every_violation() -> None:
    problem = make_problem()
    plan = make_plan(asg("act1", "A1", TUE_10), cancelled=("act1",))
    with pytest.raises(PlanInvalidError) as excinfo:
        assert_valid(problem, plan)
    assert [v.rule for v in excinfo.value.violations] == [RuleId.R1]
    assert "R1" in str(excinfo.value)
    assert "both assigned and cancelled" in str(excinfo.value)


def test_validation_is_deterministic() -> None:
    problem = make_problem()
    plan = make_plan(asg("act1", "A1", TUE_10 + 7), cancelled=("ghost",))
    assert validate(problem, plan) == validate(problem, plan)


def test_garbage_plan_is_reported_not_raised() -> None:
    from builders import move

    problem = make_problem()
    plan = make_plan(
        asg("act1", "nowhere", -5),
        asg("ghost", "A1", TUE_10),
        cancelled=("act1", "phantom"),
        moves=(move("nope", "ghost", 1, 0, 1),),
    )
    found = rule_ids(validate(problem, plan))
    assert RuleId.R1 in found
    assert RuleId.R4 in found
