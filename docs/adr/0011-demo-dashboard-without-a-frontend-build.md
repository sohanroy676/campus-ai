# ADR-0011: Demo dashboard as static pages served by FastAPI, no frontend build

## Status
Accepted

## Date
2026-10-31

## Context
The demo needs a web dashboard that walks through one disruption live: the normal campus, an
injected incident, the agents and planners at work, the proposed plans side by side, and the
updated campus once a plan is applied. The roadmap pictured "FastAPI and a simple React page".
The demo has to run offline on a laptop, with `LLM_ENABLED=false`, and must not change the frozen
evaluation code or add risk before the full run (ADR 0007).

## Decision
`smartcampus demo` serves a FastAPI app (`api/app.py`) over a `DemoSession` (`api/demo.py`). The
dashboard is one HTML page with plain JavaScript and CSS in `api/static/`, with no build step and
no CDN. The session plans with `coordinator.run.plan_with_method`, the same code as `run` and
`eval`, and changes state only by appending events to an in-memory `EventStore`. The agent
activity feed reports what the real steps returned (impact sets, room-agent offers judged by the
validator, equipment moves, solver stages, validator verdict, approval triggers). Nothing in it is
invented or animated after the fact.

Each planner is a separate request, run fastest first, so the comparison fills in as each method
finishes. All session calls run on one worker thread, because SQLite connections are bound to the
thread that opened them and one call at a time keeps a solve from racing an apply.

## Alternatives considered
- React with Vite: a node toolchain, a lockfile and a CI job for one page; and the built bundle
  or a CDN would have to be present at demo time.
- Server-sent events streaming each step: more moving parts for little gain, since each planner
  finishes in seconds on the demo scenarios.
- Fake progress animation while one big request runs: rejected, because the dashboard must not
  show anything the system did not do.

## Consequences
- `fastapi` and `uvicorn` stay an optional extra for users, but are also in the dev group so CI
  type-checks and tests the API. The API tests use a real local server and `urllib`, because
  Starlette's test client needs another package.
- The demo session is a view over the event log, so it adds no rule logic and no new state path.
- The page can move to React later without changing the API.
- The session is one shared demo for whoever opens the page; it is not a multi-user service.
