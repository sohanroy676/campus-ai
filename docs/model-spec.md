# Model spec

Source of truth for the recovery model. Code in `src/smartcampus/domain/` and `src/smartcampus/rules/` implements this document; if they disagree, fix one of them in the same commit.

## 1. Time model
- Slot length: 30 minutes. Times are integer minutes from Monday 00:00. All intervals are half-open `[start, end)`.
- Teaching day: 08:00 to 18:00, which is 20 slots per day. Activities must start and end inside it.
- Week: Monday to Friday, 5 days, 100 slots. One scenario covers one week.
- Recovery window: from the fault time to the end of that day, in the affected building plus buildings within a 10-minute walk. Everything outside the window stays fixed.
- Postponing beyond the window counts as a cancellation.

## 2. Decision variables
For each movable activity `a` (inside the recovery window):
- `x[a, r, s]` Bool: `a` is held in room `r` starting at slot `s`.
- `cancelled[a]` Bool.
- `units[a, p]` Int in `[0, pool.units]`: units of movable equipment pool `p` moved in for `a`.
- `move_start[a, p]` Int: minute at which that move starts.
- `rule_lit[R1..R8]` Bool assumption literals. Every constraint of rule `Rk` is enforced only if `rule_lit[Rk]` is true, so an infeasible core names the conflicting rules.

Activities outside the window are fixed constants.

## 3. Hard rules
Each rule is one module in `src/smartcampus/rules/` with a validator `check` and a CP-SAT `post`, both built on the same predicates.

- **R1 assignment**: every affected activity gets exactly one (room, start_slot), or `cancelled[a] = 1`. Never both, never neither.
- **R2 room_conflict**: a room hosts at most one activity per slot. A closed room (an active fault or a safety hold overlapping the slot) hosts none.
- **R3 capacity**: `room.capacity >= cohort.size`.
- **R4 room_type_and_equipment**: `room.type` is in `activity.allowed_room_types`. For each required equipment type, units present in the room plus units moved in `>= required`. Items with `movable = false` never move. A moved unit is unavailable at its source room from move start until the borrowing activity ends plus the return move time; for every slot, units in use at home + units lent out `<=` units in the pool.
- **R5 move_lead_time**: every move finishes before the class starts. The sum of `units x move_minutes_per_unit`, plus a 15-minute setup buffer, must fit between plan time and start. Concurrent moves are capped by `staff_available` (default 2 movers).
- **R6 people_conflict**: no cohort and no faculty member is in two activities in the same slot. Back-to-back classes in different buildings need `travel_minutes(b1, b2) <= 10` (the gap between classes). Otherwise they must be in the same building or have a free slot between them.
- **R7 accessibility**: if `cohort.step_free_required`, then `room.step_free = true`.
- **R8 safety_hold**: a room or equipment item with `safety_hold = true` is unusable for the whole hold. An AC failure in a GPU lab puts the room and its GPU rigs on hold.

## 4. Objective (lexicographic, not a weighted sum)
Solve the stages in order. After each stage, add the constraint "stage value `<=` its optimum" and move to the next stage. All coefficients are integers.

1. **C, cancellations**: `sum of cancelled[a]`. Unweighted count, not weighted by cohort size.
2. **P, people moved**: for each activity whose room or start changed, add `(cohort.size + number of faculty) x lateness_factor`.
   - `lateness_factor = 2` if the change happens less than 30 minutes before the start, otherwise 1.
   - Add 50 for each cohort moved a second (or later) time in the same week.
3. **D, delay**: total minutes (not slots) that activities start later than originally planned.
4. **K, cost**: equipment staff-minutes, plus 20 per cross-building move. An energy term is added here later, only if the stretch goal passes.
5. **S, start shift**: total minutes between each placed activity's new start and its original start, earlier or later. An unchanged activity adds 0.
6. **T, tie-break**: `1000 x (number of activities moved to a different building)` plus the sum of new room indices. Room index is the position of the room id after sorting room ids alphabetically, which makes the choice deterministic.

## 5. Solver
- 30 s total limit, spread across the stages as 10 / 10 / 3 / 3 / 2 / 2 s. Each stage keeps the best solution it found.
- Time tiers by scenario size (from `provenance.size`; a scenario without provenance counts as small): small keeps 30 s as above; medium and large get 90 s, split 30 / 30 / 9 / 9 / 6 / 6 s. Reason: on medium the presolve alone takes 2 to 5 s and a 10 s first stage often ends with no plan (ADR 0005). Callers can still pass explicit settings.
- `num_workers = 1` and `random_seed = 42` for tests, evaluation and the demo.
- Infeasibility: the model can always cancel, so a real "no solution" means bad input and is an error. For rejected-option explanations, each rule R1 to R8 sits behind an assumption literal and the conflicting rules are reported.

## 6. Approval triggers
`status = pending_approval` for: any cancellation; `P > 100`; any cross-building move; any change less than 30 minutes before start; any safety hold. Demo mode auto-approves and logs it.

## 7. Assumptions (reading choices, all 24 confirmed by the user on 2026-10-30)
1. One cohort per activity. R3 and stage P use `cohort.size` in the singular. Faculty is a list.
2. R5: the 15-minute setup buffer applies once per move (pool to activity). A move occupies `[move_start, move_start + units * move_minutes_per_unit + 15)` with `move_start >= plan_time` and an end at or before the activity's new start. Each move takes one mover; concurrent moves are capped at `staff_available`.
3. Resolved: source-side contention is part of R4 (see section 3). The return trip takes the same time as the outbound move (`units x move_minutes_per_unit + 15`). It only keeps the units unavailable: it does not use a mover for R5's cap and adds nothing to stage K.
4. R6 applies to cohorts and to faculty. "Back-to-back" means a gap of zero. Different buildings are allowed when `travel_minutes <= 10`; otherwise the classes need the same building or at least one free slot between them.
5. R2 covers rooms closed by faults and by holds. R8 covers holds on rooms and equipment. A room on hold can therefore violate both R2 and R8; both are named when explaining a conflict.
6. Stage P "+50 for a repeat move": counted per moved activity when `prior_moves_this_week[cohort]` plus earlier moves of that cohort in this plan (in activity id order) is at least 1. Recorded here; not implemented in the rules library.
7. Lateness ("less than 30 minutes before start") is measured from `plan_time` to the activity's original start.
8. R4 counts only usable units: a pool in the room whose hold overlaps the class does not count as present. A hold-induced shortage is therefore reported under R4; R8 reports rooms on hold and moves out of a held pool. Moved units only count toward a room if the pool normally sits in a different room.
9. R5 move length is exact: a move's planned length must equal `units x move_minutes_per_unit + 15`. There is at most one move per (pool, activity) pair, and moves also have to fit inside the week and start at or after plan time, even for a cancelled activity.
10. R8 borrow window: a move of a pool runs from its start until the class it serves ends. A hold that overlaps that window blocks the move.
11. R1 also checks that an assignment names a known room and a slot-aligned start inside the recovery window and a teaching day. A plan may be malformed (both assigned and cancelled, assigned twice, unknown ids) so the rules can report it instead of the schema rejecting it. Plan time lives on the problem, not on the plan.
12. Fixed (unaffected) activities are held to the rules too. If they already break one, the model has no solution: that is bad input, not a planning failure.
13. Contention is tracked per (home room, equipment type) group, not per individual pool. The capacity is the sum of the units of that group's pools. With one pool per room and type this is exactly "units in the pool".
14. Units in use at home by a class are `min(required, usable units present)`. The rest of its need comes from moves in, which count as lent-out units at their own source group.
15. A lent interval is `[move start, class end + return time)`. A move needs exactly one placed class end: a move for an unplaced activity, or for one placed twice with different ends, is an R4 violation. The load is checked at every interval start (minute granularity, half-open).
16. Stage P "changed" means placed in a different room or at a different start than originally; a cancelled activity counts in C only. The repeat-move surcharge is 50 x repeats per cohort, where repeats = `m` if `prior_moves_this_week >= 1`, else `max(0, m - 1)`, and `m` is the number of changed activities of that cohort. This matches assumption 6 and does not depend on activity order.
17. Stage D counts only later starts, never negative. Stage T's room-index sum covers changed activities only; "moved to a different building" means placed in a building other than the original room's. Stage K's "cross-building move" is an equipment move whose source pool sits in a different building from the room it is moved to.
18. Lateness factor is 2 when `original start - plan time < 30` minutes, including a class that has already started.
19. Resolved: stage S (start shift) sits between K and T. Among equal-cost options a class stays as close as possible to its original start, and T then picks the room. So "A2 at the original time" beats "A1 an hour earlier". S counts both directions, so it also pulls late starts back; D still counts only later starts and ranks first.
20. Unchanged by 19: when the units of a move are carried is not part of the objective. The solver returns any start that satisfies R4, R5 and R8, not the earliest or the latest.
21. `impact/` clips every fault and hold to start no earlier than plan time and drops those already over. A class that ended before plan time inside an older fault interval would otherwise break R2 as a fixed class and make the input unsolvable. The event log keeps the original intervals; only the derived problem is clipped.
22. Recovery window: from plan time (or the start of the first affected teaching day, if later) to the end of the last affected teaching day. Days are the Monday to Friday days that a clipped fault or hold overlaps; weekend-only disruptions change nothing. With nothing left to recover the window is one idle slot after plan time and no class is movable.
23. Affected classes (they must move or be cancelled): classes that overlap a clipped fault or room hold on their room, or an equipment hold on a pool in their room whose type they need. A class that is already running is affected and may only start later or be cancelled; that is why the lateness factor in assumption 18 covers started classes.
24. Movable classes: the affected ones, plus classes that have not started, lie inside the window and sit in a building within 10 minutes' walk of a disrupted room (the same limit as R6). A scenario file may state `window` and `movable_activity_ids` itself, both or neither; if neither, `impact/` derives them.

## 8. Synthetic generator
`generator/synth.py`, `generate_scenario(size, load, severity, seed)`; the same arguments always give the same file (version `GENERATOR_VERSION`, now "1"; bump it when output for a given seed changes).
- Sizes: small 2 buildings x 4 rooms, medium 3 x 7, large 5 x 8 (lecture and lab rooms alternate; GPU pools in some labs). Cohorts and faculty: two per room.
- Load: percent of room-slots in the week used by the baseline timetable (10 to 95). Random placement, so the share lands at or just under the target at high loads.
- Severity: `room` (one room fault), `building` (every room of one building), `hold` (a safety hold on the GPU pool of a class that needs it, else on the room). The disruption starts when a chosen class starts; plan time is two hours earlier. A repair overrun is an event, not scenario data, so it is not a severity.
- The baseline obeys the rules (including R6 travel). A scenario is only returned if cancelling every movable class is a valid plan.
- `provenance` (generator version, seed, size, load, severity) is written into the scenario file and copied into the run report. Hand-made scenarios have none (`null` in the report).
- Known limit: joint finds no plan within the 10 s first stage for medium at load 90, so do not freeze that combination.
