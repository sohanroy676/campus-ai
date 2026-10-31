# Roadmap

## Now (weeks 1–4: v0.1 and v0.2)
- Interviews with a timetabling officer and a facilities manager.
- Gate 1 reached (2026-10-29): `smartcampus run scenarios/dev/ac-failure.json --method joint|greedy` runs end to end. The event log, greedy baseline and CP-SAT solver are done.

## Next (weeks 5–10: v0.3 to v0.5)
- Seeded synthetic generator and the frozen 405-instance set are done (`smartcampus generate`, spec section 8). Still to do: an ITC 2019 loader (waits for the data files).
- Repair-overrun and second-event re-planning loop (the events and stale-plan rejection exist in `sim/`, and `impact/` derives the window and movable set) and approval triggers.
- Sequential and re-solve baselines and the evaluation harness are done (spec sections 9 and 10). Contract-net is built (spec section 9, `agents/`); the repair-overrun loop and approval triggers too (ADR 0008).
- Gate 2: all comparators run on the 405-instance frozen v1.0 evaluation set (20 smoke instances are separate and not counted). Progress: all 405 frozen; the full run is deferred until every feature is built (ADR 0007). If not met, the stretch goals are dropped.
- Results view through FastAPI and a simple React page.

## Later ideas (only if Gate 2 passes, or after v1.0)
- An energy cost term in the objective.
- LLM rewording of template explanations.
- Contract-net at larger scale, and event and auditorium bookings.
- Real maintenance-log calibration and robust planning over sampled repair times.

## Explicitly not planned
- Real building, HVAC or safety system control.
- Real personal data.
- Transport and shuttles, attendance, a chatbot, or full timetable generation.
- Production deployment.
- Real-world savings claims.