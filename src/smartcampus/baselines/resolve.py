"""Re-solve from scratch: plan the affected classes as if there were no timetable to protect.

The same CP-SAT model and hard rules as joint, but the minimal-change stages P (people moved),
D (delay) and S (start shift) are dropped, so only C (cancellations), K (cost) and T (tie-break)
are optimised. It gets the same complete greedy start-plan hint as joint (ADR 0010); the hint
only guides the search, the objective is what defines this comparator. The total time is the
tier's, with the time of the dropped stages split between C and K.
P, D and S are still computed on the resulting plan.
"""

from dataclasses import replace

from smartcampus.domain.plan import Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.solver.solve import SolveResult, SolverSettings, solve

C, P, D, K, S, T = range(6)  # stage indexes, in the order of STAGE_NAMES
DROPPED = frozenset({P, D, S})


def resolve_settings(tier: SolverSettings) -> SolverSettings:
    """`tier` with P, D and S skipped and their seconds given half to C and half to K."""
    seconds = list(tier.stage_seconds)
    freed = sum(seconds[i] for i in DROPPED)
    for i in DROPPED:
        seconds[i] = 0.0
    seconds[C] += freed / 2
    seconds[K] += freed / 2
    s = seconds
    return replace(tier, stage_seconds=(s[0], s[1], s[2], s[3], s[4], s[5]), skip_stages=DROPPED)


def resolve_from_scratch(
    problem: RecoveryProblem,
    tier: SolverSettings,
    *,
    based_on_version: int = 0,
    hint: Plan | None = None,
) -> SolveResult:
    return solve(problem, resolve_settings(tier), based_on_version=based_on_version, hint=hint)
