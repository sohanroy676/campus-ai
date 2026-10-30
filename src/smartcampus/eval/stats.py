"""Summaries and paired comparisons over evaluation records.

Lower is better on every metric. Methods are compared on the objective's lexicographic order
(C, P, D, K, S, T): a win is a strictly better score. Two views of the same records:

- Solved only: the instances both methods returned a plan for (the main comparison).
- Sensitivity: every instance both methods were run on. A method without a plan is scored as the
  cancel-everything plan and counts as a loss against a method with a plan.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats as scipy_stats

from smartcampus.eval.metrics import METRICS, RunRecord, metric


@dataclass(frozen=True)
class Summary:
    n: int
    median: float
    q1: float
    q3: float


@dataclass(frozen=True)
class WilcoxonResult:
    metric: str
    n: int  # instances compared
    n_nonzero: int  # instances whose scores differ (the test uses only these)
    median_difference: float  # median of (a - b); negative means a is better
    p_value: float | None  # None when no instance differs


@dataclass(frozen=True)
class Comparison:
    a: str
    b: str
    n: int
    wins: int  # a strictly better than b
    ties: int
    losses: int
    tests: tuple[WilcoxonResult, ...]


def summarize(values: Sequence[float]) -> Summary | None:
    """Median and interquartile range; None for no values."""
    if not values:
        return None
    q1, median, q3 = np.percentile(np.asarray(values, dtype=float), [25, 50, 75])
    return Summary(len(values), float(median), float(q1), float(q3))


def by_instance(records: Iterable[RunRecord]) -> dict[str, dict[str, RunRecord]]:
    table: dict[str, dict[str, RunRecord]] = defaultdict(dict)
    for record in records:
        table[record.instance][record.method] = record
    return dict(table)


def plan_rate(records: Iterable[RunRecord]) -> dict[str, tuple[int, int]]:
    """(instances with a plan, instances run) per method."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for record in records:
        counts[record.method][1] += 1
        counts[record.method][0] += int(record.solved)
    return {method: (planned, total) for method, (planned, total) in counts.items()}


def metric_summaries(records: Iterable[RunRecord], method: str) -> dict[str, Summary | None]:
    solved = [r for r in records if r.method == method and r.values is not None]
    return {
        name: summarize([metric(r.values, name) for r in solved if r.values is not None])
        for name in METRICS
    }


def time_summaries(records: Iterable[RunRecord], method: str) -> dict[str, Summary | None]:
    """Planning time, and for joint the greedy start plan inside it, on solved instances."""
    solved = [r for r in records if r.method == method and r.solved]
    return {
        "seconds": summarize([r.seconds for r in solved]),
        "start_plan_seconds": summarize([r.start_plan_seconds for r in solved]),
        "solve_seconds": summarize([r.seconds - r.start_plan_seconds for r in solved]),
    }


def compare(records: Iterable[RunRecord], a: str, b: str, *, impute: bool = False) -> Comparison:
    """`a` against `b`. With `impute`, instances without a plan are kept (see the module doc)."""
    pairs: list[tuple[RunRecord, RunRecord]] = []
    for methods in by_instance(records).values():
        ra, rb = methods.get(a), methods.get(b)
        if ra is None or rb is None:
            continue
        if impute or (ra.solved and rb.solved):
            pairs.append((ra, rb))
    wins = ties = losses = 0
    for ra, rb in pairs:
        outcome = _outcome(ra, rb)
        wins += outcome < 0
        ties += outcome == 0
        losses += outcome > 0
    tests = tuple(_wilcoxon(name, pairs) for name in METRICS)
    return Comparison(a, b, len(pairs), wins, ties, losses, tests)


def _outcome(a: RunRecord, b: RunRecord) -> int:
    """-1 if a wins, 0 for a tie, 1 if a loses."""
    if a.solved != b.solved:
        return 1 if not a.solved else -1  # a method without a plan loses
    va, vb = a.effective_values(), b.effective_values()
    return (va > vb) - (va < vb)


def _wilcoxon(name: str, pairs: Sequence[tuple[RunRecord, RunRecord]]) -> WilcoxonResult:
    diffs = np.array(
        [
            metric(ra.effective_values(), name) - metric(rb.effective_values(), name)
            for ra, rb in pairs
        ],
        dtype=float,
    )
    nonzero = int(np.count_nonzero(diffs))
    median = float(np.median(diffs)) if len(diffs) else 0.0
    p_value: float | None = None
    if nonzero:
        p_value = float(scipy_stats.wilcoxon(diffs, alternative="two-sided").pvalue)
    return WilcoxonResult(name, len(diffs), nonzero, median, p_value)
