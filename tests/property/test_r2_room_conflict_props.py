from builders import evolve
from hypothesis import assume, given
from hypothesis import strategies as st
from strategies import plans, problems, without_activity

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.base import Violation
from smartcampus.rules.r2_room_conflict import check


def normalised(violations: list[Violation]) -> list[tuple[str, tuple[str, ...]]]:
    return sorted((v.message, v.activity_ids) for v in violations)


@given(st.data())
def test_cancelling_an_activity_never_adds_conflicts(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    assume(plan.assignments)
    victim = data.draw(st.sampled_from([a.activity_id for a in plan.assignments]))
    assert len(check(problem, without_activity(plan, victim))) <= len(check(problem, plan))


@given(problems(all_movable=True))
def test_cancelling_everything_leaves_no_room_conflict(problem: RecoveryProblem) -> None:
    everything = Plan(based_on_version=0, cancelled=problem.movable_activity_ids)
    assert check(problem, everything) == []


@given(st.data())
def test_result_does_not_depend_on_assignment_order(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    flipped = evolve(plan, assignments=tuple(reversed(plan.assignments)))
    assert normalised(check(problem, flipped)) == normalised(check(problem, plan))
