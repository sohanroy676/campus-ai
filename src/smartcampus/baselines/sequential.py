"""Sequential per-domain repair: rooms, then equipment, then timing (docs/model-spec.md section 9).

Three passes, each a CP-SAT solve of the same model and hard rules as joint. A pass fixes what the
earlier passes decided and only opens its own domain, so no pass can trade one domain against
another. No rule logic lives here: the passes only fix or forbid decision variables.

1. Rooms: every movable class keeps its original start and no equipment moves. Stages C, P, T.
2. Equipment: classes cancelled by pass 1 are retried at their original start with equipment
   moves allowed; the rest stay as they are. Stages C, K, T.
3. Timing: classes still cancelled are retried with a free start and equipment moves; the rest stay
   as they are. Stages C, D, S, T.

The total time is the tier's: each pass gets the tier's seconds for its stages, scaled so that
the three passes together use the tier's total.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.rules.variables import DecisionVars
from smartcampus.solver.objective import evaluate
from smartcampus.solver.solve import SolveResult, SolverSettings, StageReport, solve

C, P, D, K, S, T = range(6)  # stage indexes, in the order of STAGE_NAMES


@dataclass(frozen=True)
class _Pass:
    name: str
    stages: tuple[int, ...]  # the stages this pass optimises
    moves_allowed: bool
    start_free: bool
    only_cancelled: bool  # open only the classes the previous pass cancelled


PASSES = (
    _Pass("rooms", (C, P, T), moves_allowed=False, start_free=False, only_cancelled=False),
    _Pass("equipment", (C, K, T), moves_allowed=True, start_free=False, only_cancelled=True),
    _Pass("timing", (C, D, S, T), moves_allowed=True, start_free=True, only_cancelled=True),
)


def pass_settings(tier: SolverSettings) -> tuple[SolverSettings, ...]:
    """One settings per pass: its own stages only, seconds scaled to share the tier's total."""
    total = sum(tier.stage_seconds)
    scale = total / sum(tier.stage_seconds[i] for p in PASSES for i in p.stages)
    out = []
    for p in PASSES:
        seconds = [tier.stage_seconds[i] * scale if i in p.stages else 0.0 for i in range(6)]
        skipped = frozenset(range(6)) - frozenset(p.stages)
        out.append(
            replace(
                tier,
                stage_seconds=(
                    seconds[0],
                    seconds[1],
                    seconds[2],
                    seconds[3],
                    seconds[4],
                    seconds[5],
                ),
                skip_stages=skipped,
            )
        )
    return tuple(out)


def sequential(
    problem: RecoveryProblem, tier: SolverSettings, *, based_on_version: int = 0
) -> SolveResult:
    """A valid plan, or the solver's `InfeasibleInputError` / `NoSolutionError`."""
    previous: Plan | None = None
    reports: list[StageReport] = []
    for spec, settings in zip(PASSES, pass_settings(tier), strict=True):
        free = (
            previous.cancelled & problem.movable_activity_ids
            if previous is not None and spec.only_cancelled
            else problem.movable_activity_ids
        )
        solved = solve(
            problem,
            settings,
            based_on_version=based_on_version,
            hint=previous,
            restrict=_restriction(spec, previous, frozenset(free)),
        )
        previous = solved.plan
        reports += [replace(r, name=f"{spec.name}:{r.name}") for r in solved.stages]
    assert previous is not None
    return SolveResult(previous, evaluate(problem, previous), tuple(reports))


def _restriction(
    spec: _Pass, previous: Plan | None, free: frozenset[str]
) -> Callable[[DecisionVars], None]:
    def restrict(ctx: DecisionVars) -> None:
        model = ctx.model
        placed = {a.activity_id: a for a in previous.assignments} if previous else {}
        moves = {(m.activity_id, m.pool_id): m for m in previous.moves} if previous else {}
        for activity_id in ctx.cancelled:  # exactly the movable classes
            keys = [key for key in ctx.units if key[0] == activity_id]
            if activity_id in free:
                for option in ctx.options[activity_id]:
                    keeps_start = spec.start_free or option.start == option.activity.start_min
                    if option.var is not None and not keeps_start:
                        model.add(option.var == 0)
                if not spec.moves_allowed:
                    for key in keys:
                        model.add(ctx.units[key] == 0)
                continue
            # Held at what the earlier passes decided.
            assignment = placed.get(activity_id)
            for option in ctx.options[activity_id]:
                if option.var is not None:
                    same = assignment is not None and (
                        assignment.room_id,
                        assignment.start_min,
                    ) == (
                        option.room.id,
                        option.start,
                    )
                    model.add(option.var == int(same))
            model.add(ctx.cancelled[activity_id] == int(assignment is None))
            for key in keys:
                move = moves.get(key)
                model.add(ctx.moved[key] == int(move is not None))
                if move is not None:
                    model.add(ctx.units[key] == move.units)
                    model.add(ctx.move_start[key] == move.start_min)

    return restrict
