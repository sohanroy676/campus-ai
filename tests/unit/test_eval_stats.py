from dataclasses import replace

import pytest

from smartcampus.eval.metrics import NO_PLAN, PLAN, RunRecord
from smartcampus.eval.stats import (
    by_instance,
    compare,
    metric_summaries,
    plan_rate,
    summarize,
    time_summaries,
)
from smartcampus.solver.objective import StageValues

CANCEL_ALL = StageValues(5, 100, 0, 0, 0, 0)


def values(c: int = 0, p: int = 0, d: int = 0, k: int = 0, s: int = 0, t: int = 0) -> StageValues:
    return StageValues(c, p, d, k, s, t)


def record(
    instance: str,
    method: str,
    result: StageValues | None,
    seconds: float = 1.0,
    start_plan: float = 0.0,
) -> RunRecord:
    return RunRecord(
        instance=instance,
        size="small",
        load=50,
        severity="room",
        seed=1,
        method=method,
        status=PLAN if result is not None else NO_PLAN,
        values=result,
        imputed=CANCEL_ALL,
        seconds=seconds if result is not None else 0.0,
        start_plan_seconds=start_plan,
    )


def test_median_and_iqr() -> None:
    summary = summarize([1, 2, 3, 4, 100])
    assert summary is not None
    assert (summary.n, summary.median, summary.q1, summary.q3) == (5, 3, 2, 4)
    assert summarize([]) is None
    single = summarize([7])
    assert single is not None and (single.median, single.q1, single.q3) == (7, 7, 7)


def test_plan_rate_counts_methods_separately() -> None:
    records = [
        record("a", "joint", values()),
        record("b", "joint", None),
        record("a", "greedy", values()),
        record("b", "greedy", values()),
    ]
    assert plan_rate(records) == {"joint": (1, 2), "greedy": (2, 2)}


def test_summaries_use_only_solved_runs() -> None:
    records = [record("a", "joint", values(p=10)), record("b", "joint", None)]
    summary = metric_summaries(records, "joint")["people_moved"]
    assert summary is not None and summary.n == 1 and summary.median == 10
    assert metric_summaries(records, "greedy")["people_moved"] is None


def test_time_summaries_split_the_start_plan_from_the_solver() -> None:
    records = [record("a", "joint", values(), seconds=10.0, start_plan=4.0)]
    t = time_summaries(records, "joint")
    assert t["seconds"] is not None and t["seconds"].median == 10.0
    assert t["start_plan_seconds"] is not None and t["start_plan_seconds"].median == 4.0
    assert t["solve_seconds"] is not None and t["solve_seconds"].median == 6.0


def test_win_tie_loss_follow_the_lexicographic_order() -> None:
    records = [
        record("a", "joint", values(p=5)),
        record("a", "greedy", values(p=9)),  # joint wins on P
        record("b", "joint", values(p=5, k=9)),
        record("b", "greedy", values(p=5, k=9)),  # tie
        record("c", "joint", values(c=1)),
        record("c", "greedy", values(p=999)),  # joint loses: C comes first
    ]
    result = compare(records, "joint", "greedy")
    assert (result.n, result.wins, result.ties, result.losses) == (3, 1, 1, 1)


def test_wilcoxon_reports_the_median_difference_and_a_p_value() -> None:
    records = []
    for i in range(10):
        records += [
            record(f"i{i}", "joint", values(p=i)),
            record(f"i{i}", "greedy", values(p=i + 5 + i)),
        ]
    result = compare(records, "joint", "greedy")
    test = next(t for t in result.tests if t.metric == "people_moved")
    assert test.n == 10 and test.n_nonzero == 10 and test.median_difference < 0
    assert test.p_value is not None and test.p_value < 0.01


def test_identical_scores_give_no_p_value_instead_of_an_error() -> None:
    records = [record("a", "joint", values(p=3)), record("a", "greedy", values(p=3))]
    for test in compare(records, "joint", "greedy").tests:
        assert test.p_value is None and test.n_nonzero == 0 and test.median_difference == 0


def test_no_shared_instances_compare_cleanly() -> None:
    records = [record("a", "joint", values()), record("b", "greedy", values())]
    result = compare(records, "joint", "greedy")
    assert (result.n, result.wins, result.ties, result.losses) == (0, 0, 0, 0)
    assert all(t.p_value is None for t in result.tests)


def test_main_view_drops_instances_a_method_did_not_solve() -> None:
    records = [
        record("a", "joint", values(p=1)),
        record("a", "greedy", values(p=2)),
        record("b", "joint", None),
        record("b", "greedy", values(p=2)),
    ]
    main = compare(records, "joint", "greedy")
    assert (main.n, main.wins, main.losses) == (1, 1, 0)


def test_sensitivity_counts_a_missing_plan_as_a_loss_and_imputes_its_score() -> None:
    records = [
        record("a", "joint", values(p=1)),
        record("a", "greedy", values(p=2)),
        record("b", "joint", None),
        record("b", "greedy", values(p=2)),
        record("c", "joint", None),
        record("c", "greedy", None),
    ]
    result = compare(records, "joint", "greedy", impute=True)
    assert (result.n, result.wins, result.ties, result.losses) == (3, 1, 1, 1)
    test = next(t for t in result.tests if t.metric == "cancellations")
    assert test.n == 3 and test.n_nonzero == 1  # only "b" differs: 5 cancelled against 0


def test_a_missing_plan_loses_even_when_its_imputed_score_would_win() -> None:
    cheap = StageValues(0, 0, 0, 0, 0, 0)
    joint = replace(record("a", "joint", None), imputed=cheap)
    result = compare([joint, record("a", "greedy", values(c=3))], "joint", "greedy", impute=True)
    assert (result.wins, result.losses) == (0, 1)


def test_records_survive_a_round_trip_through_json() -> None:
    for original in (
        record("a", "joint", values(1, 2, 3, 4, 5, 6), 2.5, 1.0),
        record("b", "x", None),
    ):
        assert RunRecord.from_json(original.to_json()) == original


def test_by_instance_groups_methods() -> None:
    table = by_instance([record("a", "joint", values()), record("a", "greedy", values())])
    assert set(table["a"]) == {"joint", "greedy"}


@pytest.mark.parametrize("bad", ["", "{", '{"instance": "a"}'])
def test_a_damaged_record_line_is_an_error(bad: str) -> None:
    with pytest.raises((ValueError, KeyError, TypeError)):
        RunRecord.from_json(bad)
