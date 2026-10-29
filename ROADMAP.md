# Roadmap

## Now (weeks 1–4: v0.1 and v0.2)
- Interviews with a timetabling officer and a facilities manager.
- Gate 1 reached (2026-10-29): `smartcampus run scenarios/dev/ac-failure.json --method joint|greedy` runs end to end. The event log, greedy baseline and CP-SAT solver are done.

## Next (weeks 5–10: v0.3 to v0.5)
- Joint room + equipment + timing model and a seeded ITC 2019 generator.
- Repair-overrun and second-event re-planning loop (the events and stale-plan rejection exist in `sim/`), `impact/` and approval triggers.
- Sequential and re-solve baselines, a contract-net variant and the evaluation harness.
- Gate 2: all comparators run on 100+ scenarios. If not, the stretch goals are dropped.
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