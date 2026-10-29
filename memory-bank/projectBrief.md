# Project brief

## What and who
A simulated campus that recovers from disruptions, such as a lab lost to an AC failure. It re-plans rooms, equipment and timing together in one CP-SAT model while changing as little as possible. It is built for the timetabling officer who approves re-plans. Students, faculty and examiners judge it by the evidence it produces.

## v1 goal
Show, on about 400 generated scenarios, whether joint minimal-change recovery beats sequential per-domain repair. Also show whether contract-net negotiation between agents can match a centralized solver.

## Success criteria
- No plan from our system breaks a hard rule. The shared rule library checks every plan.
- Every scenario gets either a valid plan or a list of the rules that conflict.
- All 5 comparators run on the frozen instance set: greedy, sequential, re-solve from scratch, joint CP-SAT and contract-net.
- Results are reported as medians and IQR, win/tie/loss counts and paired Wilcoxon tests, with threats to validity.
- Every run can be repeated exactly from its seed, generator version and solver settings.
- A timetabling officer reviews 5 plans, and their feedback is recorded.
- The demo cascade (AC failure, then a repair overrun) runs end to end, with saved outputs as a fallback.

## Explicitly out of scope
- Real building, HVAC or electrical control.
- Real student or staff data. People are modeled only as cohorts and faculty.
- Transport and shuttles, attendance, a chatbot, or generating a full timetable.
- Production deployment.
- Any claim of real-world savings.
- Letting the LLM check rules, choose plans or write state.