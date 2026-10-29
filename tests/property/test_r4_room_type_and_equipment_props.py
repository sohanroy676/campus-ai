from builders import evolve
from hypothesis import given
from hypothesis import strategies as st
from strategies import plans, problems

from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.r4_room_type_and_equipment import check


def with_extra_units(problem: RecoveryProblem, extra: int) -> RecoveryProblem:
    pools = tuple(evolve(p, units=p.units + extra) for p in problem.campus.pools)
    return evolve(problem, campus=evolve(problem.campus, pools=pools))


@given(st.data(), st.integers(0, 10))
def test_more_units_in_stock_never_add_violations(data: st.DataObject, extra: int) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, with_moves=False))
    assert len(check(with_extra_units(problem, extra), plan)) <= len(check(problem, plan))


@given(st.data())
def test_activities_needing_nothing_and_allowing_every_room_type_are_never_flagged(
    data: st.DataObject,
) -> None:
    problem = data.draw(problems())
    easy = tuple(
        evolve(a, required_equipment={}, allowed_room_types=frozenset({"lab", "lecture"}))
        for a in problem.activities
    )
    plan = data.draw(plans(problem, with_moves=False))
    assert check(evolve(problem, activities=easy), plan) == []


@given(st.data())
def test_generated_moves_have_no_structure_errors_beyond_the_movable_flag(
    data: st.DataObject,
) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem))
    messages = [v.message for v in check(problem, plan)]
    expected = sorted(
        f"pool {m.pool_id} is not movable"
        for m in plan.moves
        if not problem.campus.pool(m.pool_id).movable
    )
    assert sorted(m for m in messages if "is not movable" in m) == expected
    for word in ("unknown", "unaffected", "at most one", "exceeds"):
        assert not any(word in m for m in messages)
