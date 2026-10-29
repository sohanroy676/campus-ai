from builders import evolve
from hypothesis import given
from hypothesis import strategies as st
from strategies import plans, problems

from smartcampus.rules.r8_safety_hold import check


@given(st.data())
def test_without_holds_there_are_no_violations(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem))
    assert check(evolve(problem, holds=()), plan) == []


@given(st.data())
def test_lifting_holds_never_adds_violations(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem))
    fewer = evolve(problem, holds=problem.holds[:-1])
    assert len(check(fewer, plan)) <= len(check(problem, plan))


@given(st.data())
def test_faults_alone_are_not_safety_holds(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem))
    assert check(evolve(problem, holds=()), plan) == check(
        evolve(problem, holds=(), faults=()), plan
    )
