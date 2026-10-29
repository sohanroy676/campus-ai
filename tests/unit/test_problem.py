from typing import Any

import pytest
from builders import at, make_activity, make_problem
from pydantic import ValidationError

from smartcampus.domain.entities import Fault, SafetyHold
from smartcampus.domain.time import Interval


def test_lookups() -> None:
    problem = make_problem()
    assert problem.activity("act1").room_id == "A1"
    assert problem.cohort("c1").size == 25
    assert problem.staff_available == 2


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"movable_activity_ids": frozenset({"ghost"})}, "movable_activity_ids"),
        ({"activities": (make_activity(cohort_id="zz"),)}, "unknown cohort"),
        ({"activities": (make_activity(faculty_ids=("zz",)),)}, "unknown faculty"),
        ({"activities": (make_activity(room_id="zz"),)}, "unknown room"),
        ({"activities": (make_activity(), make_activity())}, "duplicate activity"),
        (
            {
                "faults": (
                    Fault(id="x", room_id="zz", kind="ac", interval=Interval(start=0, end=10)),
                )
            },
            "fault in unknown room",
        ),
        (
            {
                "holds": (
                    SafetyHold(
                        target_kind="equipment", target_id="zz", interval=Interval(start=0, end=10)
                    ),
                )
            },
            "unknown equipment",
        ),
        ({"staff_available": 0}, "staff_available"),
        ({"plan_time_min": -1}, "plan_time_min"),
    ],
)
def test_problem_rejects_bad_references(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        make_problem(**overrides)


def test_hold_on_a_known_pool_is_accepted() -> None:
    hold = SafetyHold(
        target_kind="equipment", target_id="gpu", interval=Interval(start=at(1, 9), end=at(1, 12))
    )
    assert make_problem(holds=(hold,)).holds == (hold,)
