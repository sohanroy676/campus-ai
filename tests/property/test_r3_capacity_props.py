from builders import evolve
from hypothesis import given
from hypothesis import strategies as st
from strategies import plans, problems

from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.r3_capacity import check


def with_extra_capacity(problem: RecoveryProblem, extra: int) -> RecoveryProblem:
    rooms = tuple(evolve(r, capacity=r.capacity + extra) for r in problem.campus.rooms)
    return evolve(problem, campus=evolve(problem.campus, rooms=rooms))


@given(st.data(), st.integers(0, 100))
def test_bigger_rooms_never_add_violations(data: st.DataObject, extra: int) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    assert len(check(with_extra_capacity(problem, extra), plan)) <= len(check(problem, plan))


@given(st.data())
def test_huge_rooms_remove_every_violation(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    assert check(with_extra_capacity(problem, 10_000), plan) == []


@given(st.data())
def test_every_violation_is_a_real_shortfall(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, wild=True))
    for violation in check(problem, plan):
        [activity_id], [room_id] = violation.activity_ids, violation.room_ids
        size = problem.cohort(problem.activity(activity_id).cohort_id).size
        assert problem.campus.room(room_id).capacity < size
