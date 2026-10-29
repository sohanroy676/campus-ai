# Architecture

## Folder tree
```
smart-campus/
  src/smartcampus/
    domain/        # Pydantic entities: Room, Cohort, Activity, Fault, Plan...; time.py (slots)
    sim/           # event log store, state projection, simulation clock, fault injector
    generator/     # ITC 2019 loader + seeded scenario generator
    impact/        # finds affected activities, cohorts, faculty in the recovery window
    agents/        # resource.py, equipment.py, maintenance.py, contract_net.py
    rules/         # shared hard-rule library + plan validator (single source of truth)
    solver/        # CP-SAT model builder, lexicographic stages, conflict explanation
    baselines/     # greedy.py, sequential.py, rescratch.py
    coordinator/   # recovery loop, approval triggers, stale-plan check
    eval/          # metrics.py, harness.py, stats.py (Wilcoxon, performance profiles)
    reporting/     # JSON report, text templates, optional llm.py
    api/           # FastAPI app (v0.5+)
    cli.py         # Typer entry point: generate, run, compare, eval
  tests/{unit,property,golden}/
  scenarios/{dev,frozen}/
  data/itc2019/    # gitignored
  web/             # React results view (v0.5+)
  var/             # SQLite db, gitignored
  .claude/        # rules, commands, settings
  .env.example
```

## How an incident flows through the system
1. A `FaultOccurred` event (e.g. AI-Lab-01 closed Tue 10:00, AC failure) is appended to the event log.
2. `sim` rebuilds state at the new version. The maintenance agent records the fault and its repair-time estimate. The true repair time stays hidden from the planner.
3. `impact` finds the affected activities, cohorts and faculty in the recovery window (that day and building, plus buildings within 10 minutes' walk).
4. Agents generate candidates. The resource agent proposes rooms and slots, and the equipment agent proposes moves with staff-minutes. Agents never write state.
5. `solver` builds one CP-SAT model from `rules` and solves it in lexicographic stages: cancellations, then people moved, then delay, then cost, then the tie-break.
6. `rules.validator` re-checks the full plan with the same rule library. A failure is a bug and raises an error.
7. `coordinator` checks that the plan's state version is still current, then applies the approval triggers. Any cancellation, more than 100 people moved, a cross-building move, a change within 30 minutes of start, or a safety hold all need approval. Demo mode auto-approves these.
8. Applying the plan appends a `PlanApplied` event. `reporting` writes the decision log and metrics.
9. A later event, such as `RepairOverrun`, restarts the loop. Plans built on an older state version are marked stale.

## Key modules
| Module | Responsibility |
| --- | --- |
| `rules` | Each hard rule written once; used by the solver builder and the validator |
| `solver` | Joint recovery model; infeasibility reasons via assumption literals |
| `sim` | Append-only event log is the only write path; replay and reset |
| `agents` | Candidate generation; contract-net variant for the negotiation experiment |
| `baselines` | Greedy, sequential per-domain, re-solve from scratch |
| `eval` | Frozen instance runs, metrics, paired statistics |

## Third-party services
- OpenAI API (optional, explanations only). Configured with `LLM_ENABLED`, `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`. Keys live only in `.env`, which is gitignored, and are never hardcoded. `.env.example` lists the names with empty values.
- No other external services. The system runs fully offline with `LLM_ENABLED=false`.