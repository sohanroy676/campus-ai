from builders import evolve
from hypothesis import given
from hypothesis import strategies as st
from strategies import plans, problems

from smartcampus.rules.r7_accessibility import check


@given(st.data())
def test_all_rooms_step_free_means_no_violations(data: st.DataObject) -> None:
    problem = data.draw(problems())
    rooms = tuple(evolve(r, step_free=True) for r in problem.campus.rooms)
    ramped = evolve(problem, campus=evolve(problem.campus, rooms=rooms))
    plan = data.draw(plans(problem, with_moves=False))
    assert check(ramped, plan) == []


@given(st.data())
def test_no_cohort_needing_access_means_no_violations(data: st.DataObject) -> None:
    problem = data.draw(problems())
    cohorts = tuple(evolve(c, step_free_required=False) for c in problem.cohorts)
    plan = data.draw(plans(problem, with_moves=False))
    assert check(evolve(problem, cohorts=cohorts), plan) == []


@given(st.data())
def test_every_violation_is_a_needy_cohort_in_a_room_with_steps(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, wild=True))
    for violation in check(problem, plan):
        [activity_id], [room_id] = violation.activity_ids, violation.room_ids
        assert problem.cohort(problem.activity(activity_id).cohort_id).step_free_required
        assert not problem.campus.room(room_id).step_free
