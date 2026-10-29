"""Hypothesis strategies: small random recovery problems and plans for them (all on Tuesday)."""

from collections.abc import Callable
from typing import Any, Literal

from builders import asg, at, evolve, move
from hypothesis import assume
from hypothesis import strategies as st

from smartcampus.domain.entities import (
    Activity,
    Building,
    Campus,
    Cohort,
    EquipmentPool,
    Faculty,
    Fault,
    Room,
    SafetyHold,
    Walk,
)
from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.rules._shared import move_minutes, valid_starts

TUE = 1
DAY_OPEN = at(TUE, 8)
WINDOW = Interval(start=DAY_OPEN, end=at(TUE, 14))


def slot_minute(slot: int) -> int:
    return DAY_OPEN + 30 * slot


@st.composite
def campuses(draw: st.DrawFn) -> Campus:
    rooms = tuple(
        Room(
            id=f"R{i}",
            building_id=draw(st.sampled_from(["A", "B"])),
            type=draw(st.sampled_from(["lab", "lecture"])),
            capacity=draw(st.integers(10, 60)),
            step_free=draw(st.booleans()),
        )
        for i in range(draw(st.integers(2, 4)))
    )
    pools = tuple(
        EquipmentPool(
            id=f"P{i}",
            type="gpu",
            room_id=draw(st.sampled_from([r.id for r in rooms])),
            units=draw(st.integers(1, 4)),
            movable=draw(st.booleans()),
            move_minutes_per_unit=draw(st.sampled_from([0, 5, 10])),
        )
        for i in range(draw(st.integers(0, 2)))
    )
    walk = draw(st.sampled_from([0, 5, 10, 11, 30]))
    return Campus(
        buildings=(Building(id="A"), Building(id="B")),
        rooms=rooms,
        pools=pools,
        walks=(Walk(a="A", b="B", minutes=walk),),
    )


@st.composite
def problems(draw: st.DrawFn, *, all_movable: bool = False) -> RecoveryProblem:
    campus = draw(campuses())
    room_ids = [r.id for r in campus.rooms]
    cohorts = tuple(
        Cohort(id=f"c{i}", size=draw(st.integers(5, 60)), step_free_required=draw(st.booleans()))
        for i in range(draw(st.integers(2, 3)))
    )
    activities = []
    for i in range(draw(st.integers(1, 4))):
        duration = draw(st.integers(1, 3))
        activities.append(
            Activity(
                id=f"a{i}",
                cohort_id=draw(st.sampled_from([c.id for c in cohorts])),
                faculty_ids=tuple(
                    draw(st.lists(st.sampled_from(["f0", "f1"]), unique=True, max_size=2))
                ),
                duration_slots=duration,
                allowed_room_types=draw(
                    st.frozensets(st.sampled_from(["lab", "lecture"]), min_size=1)
                ),
                required_equipment=draw(
                    st.sampled_from([{}, {}, {"gpu": 1}, {"gpu": 2}, {"gpu": 4}])
                ),
                room_id=draw(st.sampled_from(room_ids)),
                start_min=slot_minute(draw(st.integers(0, 20 - duration))),
            )
        )
    ids = [a.id for a in activities]
    movable = (
        frozenset(ids)
        if all_movable
        else frozenset(draw(st.sets(st.sampled_from(ids), min_size=1)))
    )
    faults = []
    if draw(st.booleans()):
        first = draw(st.integers(0, 11))
        last = draw(st.integers(first + 1, 12))
        faults.append(
            Fault(
                id="fault",
                room_id=draw(st.sampled_from(room_ids)),
                kind="ac",
                interval=Interval(start=slot_minute(first), end=slot_minute(last)),
            )
        )
    holds = []
    if draw(st.booleans()):
        targets: list[tuple[Literal["room", "equipment"], str]] = [("room", r) for r in room_ids]
        targets += [("equipment", p.id) for p in campus.pools]
        kind, target = draw(st.sampled_from(targets))
        first = draw(st.integers(0, 11))
        last = draw(st.integers(first + 1, 12))
        holds.append(
            SafetyHold(
                target_kind=kind,
                target_id=target,
                interval=Interval(start=slot_minute(first), end=slot_minute(last)),
            )
        )
    return RecoveryProblem(
        campus=campus,
        cohorts=cohorts,
        faculty=(Faculty(id="f0"), Faculty(id="f1")),
        activities=tuple(activities),
        faults=tuple(faults),
        holds=tuple(holds),
        movable_activity_ids=movable,
        window=WINDOW,
        plan_time_min=at(TUE, 7) + 5 * draw(st.integers(0, 24)),
        staff_available=draw(st.integers(1, 2)),
        prior_moves_this_week=draw(
            st.dictionaries(st.sampled_from([c.id for c in cohorts]), st.integers(0, 2), max_size=2)
        ),
    )


SOUND_MODES = ("assign", "assign", "assign", "cancel")
REPRESENTABLE_MODES = (*SOUND_MODES, "neither", "both", "twice")
Mutation = Callable[[RecoveryProblem, st.DrawFn, list[Any], set[str], list[Any]], None]


def _unknown_room(problem: RecoveryProblem, draw: st.DrawFn, asgs: list[Any], *_: Any) -> None:
    asgs.append(
        asg(draw(st.sampled_from(sorted(problem.movable_activity_ids))), "ZZ", WINDOW.start)
    )


def _off_grid_start(problem: RecoveryProblem, draw: st.DrawFn, asgs: list[Any], *_: Any) -> None:
    aid = draw(st.sampled_from(sorted(problem.movable_activity_ids)))
    start = draw(st.sampled_from([WINDOW.start + 15, WINDOW.end, at(TUE + 1, 9), -30]))
    asgs.append(asg(aid, problem.campus.rooms[0].id, start))


def _ghost_assignment(problem: RecoveryProblem, draw: st.DrawFn, asgs: list[Any], *_: Any) -> None:
    asgs.append(asg("ghost", problem.campus.rooms[0].id, WINDOW.start))


def _ghost_cancel(
    problem: RecoveryProblem, draw: st.DrawFn, asgs: list[Any], cancelled: set[str], *_: Any
) -> None:
    cancelled.add("ghost")


def _exact_duplicate(problem: RecoveryProblem, draw: st.DrawFn, asgs: list[Any], *_: Any) -> None:
    if asgs:
        asgs.append(asgs[0])


def _bad_move(
    problem: RecoveryProblem,
    draw: st.DrawFn,
    asgs: list[Any],
    cancelled: set[str],
    moves: list[Any],
) -> None:
    aid = draw(st.sampled_from(sorted(problem.movable_activity_ids)))
    pool = problem.campus.pools[0] if problem.campus.pools else None
    kind = draw(st.sampled_from(["unknown_pool", "wrong_length", "too_many", "duplicate", "late"]))
    start = problem.plan_time_min + 30
    if pool is None or kind == "unknown_pool":
        moves.append(move("ZZ", aid, 1, start, 20))
    elif kind == "wrong_length":
        moves.append(move(pool.id, aid, 1, start, move_minutes(pool, 1) + 7))
    elif kind == "too_many":
        moves.append(move(pool.id, aid, pool.units + 1, start, move_minutes(pool, pool.units + 1)))
    elif kind == "duplicate":
        moves.extend([move(pool.id, aid, 1, start, move_minutes(pool, 1))] * 2)
    else:
        moves.append(move(pool.id, aid, 1, 7 * 1440 + 100, move_minutes(pool, 1)))


MUTATIONS: tuple[Mutation, ...] = (
    _unknown_room,
    _off_grid_start,
    _ghost_assignment,
    _ghost_cancel,
    _exact_duplicate,
    _bad_move,
)


@st.composite
def plans(
    draw: st.DrawFn,
    problem: RecoveryProblem,
    *,
    modes: tuple[str, ...] = SOUND_MODES,
    with_moves: bool = True,
    wild: bool = False,
) -> Plan:
    """A plan for `problem`.

    `modes` picks, per affected activity: assign / cancel (sound) or neither / both / twice
    (breaks R1 but still representable in the CP-SAT variables). `wild=True` also applies
    mutations that no CP-SAT assignment can express (unknown ids, off-grid times, bad moves).
    """
    room_ids = [r.id for r in problem.campus.rooms]
    assignments: list[Any] = []
    cancelled: set[str] = set()
    for aid in sorted(problem.movable_activity_ids):
        starts = valid_starts(problem, problem.activity(aid))
        duration = problem.activity(aid).duration_min
        # Starts that touch an earlier placement exactly, so back-to-back cases are common.
        adjacent = sorted(
            {
                s
                for earlier in assignments
                for s in (
                    earlier.start_min + problem.activity(earlier.activity_id).duration_min,
                    earlier.start_min - duration,
                )
                if s in starts
            }
        )
        start_choice = st.sampled_from(starts)
        if adjacent:
            start_choice = st.one_of(start_choice, st.sampled_from(adjacent))
        pick = st.tuples(st.sampled_from(room_ids), start_choice)
        mode = draw(st.sampled_from(modes))
        if mode in ("assign", "both", "twice"):
            assignments.append(asg(aid, *draw(pick)))
        if mode == "twice":
            second = draw(pick)
            if second != (assignments[-1].room_id, assignments[-1].start_min):
                assignments.append(asg(aid, *second))
        if mode in ("cancel", "both"):
            cancelled.add(aid)
    moves: list[Any] = []
    if with_moves:
        class_start = {a.activity_id: a.start_min for a in assignments}
        for aid in sorted(problem.movable_activity_ids):
            for pool in problem.campus.pools:
                if draw(st.booleans()):
                    units = draw(st.integers(1, pool.units))
                    length = move_minutes(pool, units)
                    if aid in class_start and draw(st.booleans()):
                        # Finish just before class, so only the mover cap can go wrong.
                        start = class_start[aid] - length - draw(st.sampled_from([0, 0, 5, 10, 30]))
                    else:
                        start = problem.plan_time_min + 5 * draw(st.integers(-6, 60))
                    moves.append(move(pool.id, aid, units, start, length))
    if wild:
        for index in draw(st.lists(st.integers(0, len(MUTATIONS) - 1), max_size=2)):
            MUTATIONS[index](problem, draw, assignments, cancelled, moves)
    return Plan(
        based_on_version=0,
        assignments=tuple(assignments),
        cancelled=frozenset(cancelled),
        moves=tuple(moves),
    )


def without_activity(plan: Plan, activity_id: str) -> Plan:
    """The plan with `activity_id` cancelled instead of placed (and its moves dropped)."""
    return evolve(
        plan,
        assignments=tuple(a for a in plan.assignments if a.activity_id != activity_id),
        cancelled=plan.cancelled | {activity_id},
        moves=tuple(m for m in plan.moves if m.activity_id != activity_id),
    )


@st.composite
def borrowing_problems(draw: st.DrawFn) -> RecoveryProblem:
    """Every class needs gpus and fits any room type, and every pool can be moved."""
    base = draw(problems(all_movable=True))
    assume(base.campus.pools)
    activities = tuple(
        evolve(
            a,
            allowed_room_types=frozenset({"lab", "lecture"}),
            required_equipment={"gpu": draw(st.integers(1, 4))},
        )
        for a in base.activities
    )
    pools = tuple(evolve(p, movable=True) for p in base.campus.pools)
    return evolve(base, activities=activities, campus=evolve(base.campus, pools=pools))


@st.composite
def borrowing_plans(draw: st.DrawFn, problem: RecoveryProblem) -> Plan:
    """Place every class and move in exactly the gpus its room lacks, so only stock can go wrong."""
    plan = draw(plans(problem, modes=("assign",), with_moves=False))
    moves = []
    for placed in plan.assignments:
        activity = problem.activity(placed.activity_id)
        missing = activity.required_equipment["gpu"] - sum(
            p.units for p in problem.campus.pools if p.room_id == placed.room_id
        )
        for pool in problem.campus.pools:
            take = min(missing, pool.units)
            if pool.room_id == placed.room_id or take <= 0:
                continue
            length = move_minutes(pool, take)
            lead = draw(st.sampled_from([0, 10, 30]))
            moves.append(move(pool.id, activity.id, take, placed.start_min - length - lead, length))
            missing -= take
    return evolve(plan, moves=tuple(moves))
