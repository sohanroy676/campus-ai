from builders import evolve
from hypothesis import assume, given
from hypothesis import strategies as st
from strategies import plans, problems, without_activity

from smartcampus.domain.entities import Walk
from smartcampus.rules.r6_people_conflict import check


@given(st.data())
def test_cancelling_an_activity_never_adds_conflicts(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    assume(plan.assignments)
    victim = data.draw(st.sampled_from([a.activity_id for a in plan.assignments]))
    assert len(check(problem, without_activity(plan, victim))) <= len(check(problem, plan))


@given(st.data())
def test_shorter_walks_never_add_violations(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    nearby = evolve(problem.campus, walks=(Walk(a="A", b="B", minutes=0),))
    assert len(check(evolve(problem, campus=nearby), plan)) <= len(check(problem, plan))


@given(st.data())
def test_activities_with_nobody_in_common_never_conflict(data: st.DataObject) -> None:
    problem = data.draw(problems())
    loners = tuple(
        evolve(a, cohort_id=f"solo{i}", faculty_ids=()) for i, a in enumerate(problem.activities)
    )
    cohorts = problem.cohorts + tuple(
        evolve(problem.cohorts[0], id=f"solo{i}") for i in range(len(loners))
    )
    isolated = evolve(problem, activities=loners, cohorts=cohorts)
    plan = data.draw(plans(isolated, with_moves=False))
    assert check(isolated, plan) == []
