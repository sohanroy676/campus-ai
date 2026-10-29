# Roadmap

## Now (weeks 1–4: v0.1 and v0.2)
- Interviews with a timetabling officer and a facilities manager.
- Event-log simulator, greedy baseline and a first CP-SAT model, run end to end from the CLI.
- Gate 1: one scenario runs end to end, baseline included.

## Next (weeks 5–10: v0.3 to v0.5)
- Joint room + equipment + timing model and a seeded ITC 2019 generator.
- Repair overruns, second events, stale-plan rejection and approval triggers.
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