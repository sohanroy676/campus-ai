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
- **R4 room_type_and_equipment**: `room.type` is in `activity.allowed_room_types`. For each required equipment type, units present in the room plus units moved in `>= required`. Items with `movable = false` never move.
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
5. **T, tie-break**: `1000 x (number of activities moved to a different building)` plus the sum of new room indices. Room index is the position of the room id after sorting room ids alphabetically, which makes the choice deterministic.

## 5. Solver
- 30 s total limit, spread across the stages as 10 / 10 / 4 / 4 / 2 s. Each stage keeps the best solution it found.
- `num_workers = 1` and `random_seed = 42` for tests, evaluation and the demo.
- Infeasibility: the model can always cancel, so a real "no solution" means bad input and is an error. For rejected-option explanations, each rule R1 to R8 sits behind an assumption literal and the conflicting rules are reported.

## 6. Approval triggers
`status = pending_approval` for: any cancellation; `P > 100`; any cross-building move; any change less than 30 minutes before start; any safety hold. Demo mode auto-approves and logs it.

## 7. Assumptions (reading choices, to confirm)
1. One cohort per activity. R3 and stage P use `cohort.size` in the singular. Faculty is a list.
2. R5: the 15-minute setup buffer applies once per move (pool to activity). A move occupies `[move_start, move_start + units * move_minutes_per_unit + 15)` with `move_start >= plan_time` and an end at or before the activity's new start. Each move takes one mover; concurrent moves are capped at `staff_available`.
3. **Open question for the user.** Equipment is not tracked at its source: nothing in R1 to R8 stops the same units being used in their home room while also moved elsewhere. I did not invent a ninth rule for it. The only limits are `units <= pool.units` per move and `movable = true`. Say so if source-side contention should become a rule. Return trips are not modeled.
4. R6 applies to cohorts and to faculty. "Back-to-back" means a gap of zero. Different buildings are allowed when `travel_minutes <= 10`; otherwise the classes need the same building or at least one free slot between them.
5. R2 covers rooms closed by faults and by holds. R8 covers holds on rooms and equipment. A room on hold can therefore violate both R2 and R8; both are named when explaining a conflict.
6. Stage P "+50 for a repeat move": counted per moved activity when `prior_moves_this_week[cohort]` plus earlier moves of that cohort in this plan (in activity id order) is at least 1. Recorded here; not implemented in the rules library.
7. Lateness ("less than 30 minutes before start") is measured from `plan_time` to the activity's original start.
8. R4 counts only usable units: a pool in the room whose hold overlaps the class does not count as present. A hold-induced shortage is therefore reported under R4; R8 reports rooms on hold and moves out of a held pool. Moved units only count toward a room if the pool normally sits in a different room.
9. R5 move length is exact: a move's planned length must equal `units x move_minutes_per_unit + 15`. There is at most one move per (pool, activity) pair, and moves also have to fit inside the week and start at or after plan time, even for a cancelled activity.
10. R8 borrow window: a move of a pool runs from its start until the class it serves ends. A hold that overlaps that window blocks the move.
11. R1 also checks that an assignment names a known room and a slot-aligned start inside the recovery window and a teaching day. A plan may be malformed (both assigned and cancelled, assigned twice, unknown ids) so the rules can report it instead of the schema rejecting it. Plan time lives on the problem, not on the plan.
12. Fixed (unaffected) activities are held to the rules too. If they already break one, the model has no solution: that is bad input, not a planning failure.
