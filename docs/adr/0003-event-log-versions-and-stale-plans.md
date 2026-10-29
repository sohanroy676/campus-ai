# ADR-0003: Event log versions and stale plans

## Status
Accepted

## Date
2026-10-29

## Context
State may change only by appending events (`sim/`). A plan is computed against one state of the world; if a later event (a repair overrun, a second fault) arrives before the plan is applied, applying it could break a hard rule the plan never saw.

## Decision
- The log is an SQLite table with one row per event. The state version is the number of events so far. Each event carries its own `version`, which must equal the state version when it is appended, so versions run 0, 1, 2, ... without gaps. A `UNIQUE` primary key on `version` backs this up against a second writer.
- A `PlanApplied` event is accepted only if `plan.based_on_version` equals the state version at that moment. A plan built on an older (or newer) state is rejected with `StalePlanError`; nothing is written.
- Events are checked against the current state before they are written (known fault for an overrun, an overrun must end later, no clock running backwards, no repeated fault id), so an invalid event never reaches the log.
- Rows cannot be updated or deleted; triggers abort both. State is the fold of the log (`sim/state.py`), so replaying a log always rebuilds the same state.

## Alternatives considered
- Store stale plans and mark them `stale`: keeps a record of the attempt, but lets a caller treat a stale plan as applied by mistake. A rejected append is harder to ignore.
- A version per entity instead of one counter: finer-grained, but a plan can depend on any room, class or pool, so one counter is the safe reading.

## Consequences
- Any new event invalidates every plan computed before it, even if the event is unrelated to that plan. The caller re-solves.
- Events are not checked against the campus at append time (a fault in an unknown room is caught when the state is turned into a `RecoveryProblem`). The CLI seeds events from an already validated problem.
