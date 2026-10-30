"""The problem to re-plan after a later event: the timetable as the applied plans left it.

Rules (docs/adr/0008-approval-and-replanning-base.md):
- Applied plans are folded into the activities: moved classes sit in their new room and start, and
  classes an approved plan cancelled are gone for good.
- Plan time is the log's clock. Cohorts moved by earlier plans count as moved already this week,
  so the existing repeat-move cost applies.
- A class an earlier plan moved or lent equipment to, and that has not started, is recoverable
  again (the window grows to hold it): its equipment moves are not part of the new problem, so the
  new plan must provide them. A class that has already started keeps its room and start, and its
  equipment is taken as delivered (`required_equipment` is cleared).
"""

from collections import Counter

from smartcampus.domain.entities import Activity
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval, day_of, end_of_teaching_day
from smartcampus.impact.derive import derive_recovery
from smartcampus.sim.state import SimState


def replan_problem(base: RecoveryProblem, state: SimState) -> RecoveryProblem:
    """`base` as it stands after `state`, with window and movable set derived again."""
    activities: dict[str, Activity] = {a.id: a for a in base.activities}
    moved: Counter[str] = Counter()
    touched: set[str] = set()
    for plan in state.applied_plans:
        for activity_id in plan.cancelled:
            activities.pop(activity_id, None)
        for asg in plan.assignments:
            current = activities.get(asg.activity_id)
            if current is None or (asg.room_id, asg.start_min) == (
                current.room_id,
                current.start_min,
            ):
                continue
            moved[current.cohort_id] += 1
            touched.add(current.id)
            activities[current.id] = current.model_copy(
                update={"room_id": asg.room_id, "start_min": asg.start_min}
            )
        touched |= {m.activity_id for m in plan.moves if m.activity_id in activities}

    now = state.now_min
    for activity_id in touched:
        activity = activities[activity_id]
        if activity.start_min < now and activity.required_equipment:
            activities[activity_id] = activity.model_copy(update={"required_equipment": {}})

    prior = {cohort: base.prior_moves_this_week.get(cohort, 0) + n for cohort, n in moved.items()}
    rebuilt = RecoveryProblem.model_validate(
        {
            **dict(base),
            "activities": tuple(activities.values()),
            "faults": state.faults,
            "holds": state.holds,
            "plan_time_min": now,
            "prior_moves_this_week": {**base.prior_moves_this_week, **prior},
            "movable_activity_ids": frozenset(),
        }
    )
    derived = derive_recovery(rebuilt)

    again = {a for a in touched if activities[a].start_min >= now}
    if not again:
        return derived
    spans = [activities[a] for a in again]
    window = Interval(
        start=min(derived.window.start, *(a.start_min for a in spans)),
        end=max(
            derived.window.end,
            *(end_of_teaching_day(day_of(a.start_min + a.duration_min - 1)) for a in spans),
        ),
    )
    return RecoveryProblem.model_validate(
        {
            **dict(derived),
            "window": window,
            "movable_activity_ids": derived.movable_activity_ids | again,
        }
    )
