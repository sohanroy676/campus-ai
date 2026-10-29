import pytest
from pydantic import ValidationError

from smartcampus.domain.plan import Assignment, EquipmentMove, Plan, PlanStatus


def test_empty_plan_defaults() -> None:
    plan = Plan(based_on_version=0)
    assert plan.status is PlanStatus.PROPOSED
    assert plan.assignments == ()
    assert plan.cancelled == frozenset()


def test_malformed_plan_is_representable_so_r1_can_report_it() -> None:
    plan = Plan(
        based_on_version=1,
        assignments=(Assignment(activity_id="a", room_id="A1", start_min=600),),
        cancelled=frozenset({"a"}),
    )
    assert "a" in plan.cancelled


@pytest.mark.parametrize(("start", "end"), [(100, 100), (100, 90)])
def test_move_must_end_after_start(start: int, end: int) -> None:
    with pytest.raises(ValidationError):
        EquipmentMove(pool_id="gpu", activity_id="a", units=1, start_min=start, end_min=end)


def test_move_needs_positive_units() -> None:
    with pytest.raises(ValidationError):
        EquipmentMove(pool_id="gpu", activity_id="a", units=0, start_min=0, end_min=10)


def test_negative_version_rejected() -> None:
    with pytest.raises(ValidationError):
        Plan(based_on_version=-1)


def test_status_values_match_spec() -> None:
    assert {s.value for s in PlanStatus} == {
        "proposed",
        "pending_approval",
        "approved",
        "applied",
        "stale",
        "rejected",
    }
