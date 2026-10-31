# ADR-0008: Approval record and the re-planning base

## Status
Accepted

## Date
2026-10-30

## Context
Spec section 6 asks for approval triggers, and the demo cascade (AC failure, then a repair overrun) needs a second plan built after the first was applied. Two questions: where is approval recorded, and what is the problem the second plan is built from? `run_scenario` and the evaluation must not change, because their records would go stale.

## Decision
- Triggers are a pure function in `coordinator/approval.py`, on top of a plan that already passed the hard rules. They are policy, not rules, so they do not live in `rules/`.
- Approval is a field on `PlanApplied` (`approver` and the triggers fired), not its own event. An approval event would add one to the state version and make the plan it approves stale (ADR 0003).
- A plan that fires a trigger and is not auto-approved is held by the coordinator, never written to the log. The next event makes it stale and a new plan is built.
- The re-planning base is the original problem with the applied plans folded in, plan time set to the log's clock, earlier moves counted in `prior_moves_this_week`, and window and movable set derived again (`coordinator/replan.py`). Classes an earlier plan touched and that have not started are recoverable again; the window grows to hold them. A started class keeps its place and its equipment is taken as delivered. A class an approved plan cancelled stays cancelled.
- Cascades run through `smartcampus cascade` and `coordinator.loop.recover`. `run`, `run_scenario` and the eval are unchanged in behaviour (the planning step was moved into `plan_with_method`).

## Alternatives considered
- A separate `PlanApproved` event: a clearer log, but it stales the plan it approves unless the version rules change.
- Re-planning from the original timetable: simple, but then people moved in round 1 would not count, and the new plan could contradict what was already applied.
- Letting an approved cancellation be reversed in later rounds: more flexible, but a cancelled class has told its students.

## Consequences
- The equipment borrowed for a started class is not counted as lent out in later rounds, so a unit still on loan may look free to the second plan. Small, and only for classes already running.
- A scripted cascade is not an evaluation arm; the five comparators are measured on single disruptions only.
