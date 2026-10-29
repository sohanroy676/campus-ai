from builders import evolve
from hypothesis import assume, given
from hypothesis import strategies as st
from strategies import plans, problems

from smartcampus.rules.r1_assignment import check


@given(st.data())
def test_sound_plans_satisfy_r1(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    assert check(problem, plan) == []


@given(st.data())
def test_cancelling_an_assigned_activity_as_well_is_reported(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    assume(plan.assignments)
    victim = data.draw(st.sampled_from([a.activity_id for a in plan.assignments]))
    both = evolve(plan, cancelled=plan.cancelled | {victim})
    assert [v.activity_ids for v in check(problem, both)] == [(victim,)]


@given(st.data())
def test_dropping_a_placement_leaves_the_activity_unresolved(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    assume(plan.assignments)
    victim = plan.assignments[0].activity_id
    dropped = evolve(plan, assignments=plan.assignments[1:])
    assert [v.activity_ids for v in check(problem, dropped)] == [(victim,)]


@given(st.data())
def test_any_garbage_is_reported_without_raising(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, wild=True))
    for violation in check(problem, plan):
        assert violation.message
