# Live demo dashboard

A web dashboard that shows one campus disruption end to end: the system detects the problem,
the agents and planners work on it, the plans are compared, and the chosen plan updates the
digital campus. It runs offline, with no LLM, on the same code as `smartcampus run` and `eval`.

## Start it

```
uv sync --extra api
uv run smartcampus demo            # http://127.0.0.1:8000/
uv run smartcampus demo --scenario generated-small --port 8080
```

Scenarios (pick them in the header too):

| id | campus | what it shows |
|---|---|---|
| `ac-failure` (default) | 4 rooms, 2 buildings, 4 classes | The AC demo: joint moves 26 people, greedy 55 |
| `ac-cascade` | the AC demo plus a robotics lab | A repair overrun after the first plan |
| `generated-small` | 8 rooms, 246 classes (seeded, small, load 75, seed 2) | Joint moves 38 people, greedy 109; every plan fires an approval trigger |

## The panels

- **Campus Overview**: buildings, rooms, labs, equipment, room status, and a day timetable
  (rooms by time) with the out-of-use room hatched and the hit classes outlined in red.
- **Incident Panel**: inject a fault (room, kind, day, from, until), see the impact (recovery
  window, classes hit, classes that may move), and later report a repair overrun.
- **Agent Activity**: what each step returned, in order: maintenance (event logged), impact
  analysis, room agents (offers, and how many rooms the validator accepts), equipment agent
  (moves), each planner and the CP-SAT stages, the rule validator, approval triggers, the
  coordinator applying a plan.
- **Solution Comparison**: the five methods (greedy, sequential repair, contract-net agents,
  re-solve, joint CP-SAT) with cancellations, people moved, delay, equipment cost, classes changed,
  approval and planning time. Best by the lexicographic score; ties go to joint.
- **Updated Campus State**: click a row to preview that plan on the timetable (moved classes in
  green, their old place dashed). Apply writes it to the event log and shows the campus after it.
- **Performance Metrics**: tiles, bars per method (people moved, cancellations, delay, time) and
  the event log.

## A five-minute script

1. Open the dashboard. Show the campus: rooms, the GPU pool in AI-Lab-01, Tuesday's classes.
2. The form is filled with the scenario's incident (AC failure in AI-Lab-01, Tue 10:00 to 14:00).
   Click **Inject incident**. AI-Lab-01 turns red and `ml-lab` is outlined.
3. The planners start at once. Watch Agent Activity: the room agents find two rooms that can take
   `ml-lab`, the equipment agent books three GPUs, then each planner reports, CP-SAT stage by stage,
   and the validator re-checks every plan against R1 to R8.
4. In Solution Comparison, joint and sequential move 26 people, greedy and contract-net 55. Click
   the joint row to preview it below.
5. Click **Apply** on joint. The log gets a `plan_applied` event, the timetable shows `ml-lab` in
   AI-Lab-02 at 09:00, and the GPUs on loan.
6. Optional, on `ac-cascade`: report a repair overrun (reported 12:00, new end 16:00) to show the
   system re-planning from the applied state.

Switch to `generated-small` to show a fuller week: on Friday, joint moves 38 people against
greedy's 109 and needs the officer for a cross-building move only.

## Notes

- The session keeps one event log in memory; **Reset** or switching scenario starts over.
- Applying a plan that fires an approval trigger records the dashboard user as the officer.
- Design choices: ADR 0011.
