from builders import evolve
from hypothesis import given
from hypothesis import strategies as st
from strategies import plans, problems

from smartcampus.rules.r5_move_lead_time import check


@given(st.data())
def test_more_movers_never_add_violations(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem))
    more = evolve(problem, staff_available=problem.staff_available + 1)
    assert len(check(more, plan)) <= len(check(problem, plan))


@given(st.data(), st.integers(0, 600))
def test_planning_earlier_never_adds_violations(data: st.DataObject, earlier: int) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem))
    sooner = evolve(problem, plan_time_min=max(0, problem.plan_time_min - earlier))
    assert len(check(sooner, plan)) <= len(check(problem, plan))


@given(st.data())
def test_a_plan_without_moves_never_breaks_r5(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    assert check(problem, plan) == []


@given(st.data())
def test_every_moved_pool_cost_matches_units_and_setup(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem))
    for m in plan.moves:
        pool = problem.campus.pool(m.pool_id)
        assert m.end_min - m.start_min == m.units * pool.move_minutes_per_unit + 15
    assert not any("takes" in v.message for v in check(problem, plan))
