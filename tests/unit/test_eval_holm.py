import itertools
from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from smartcampus.eval.metrics import NO_PLAN, PLAN, RunRecord
from smartcampus.eval.report import format_report
from smartcampus.eval.stats import adjust, compare, holm, limit_counts
from smartcampus.solver.objective import StageValues

CANCEL_ALL = StageValues(5, 100, 0, 0, 0, 0)


def rec(instance: str, method: str, c: int, p: int, **flags: bool) -> RunRecord:
    return RunRecord(
        instance=instance,
        size="small",
        load=50,
        severity="room",
        seed=1,
        method=method,
        status=PLAN,
        values=StageValues(c, p, 0, 0, 0, 0),
        imputed=CANCEL_ALL,
        seconds=2.0,
        start_plan_seconds=0.0,
        stage_seconds=[10.0, 10.0, 3.0, 3.0, 2.0, 2.0] if method != "greedy" else [],
        **flags,
    )


def test_holm_matches_the_textbook_example() -> None:
    # p = 0.01, 0.04, 0.03, 0.005 with m = 4: sorted 0.005*4, 0.01*3, 0.03*2, 0.04*1, made monotone
    assert holm([0.01, 0.04, 0.03, 0.005]) == [0.03, 0.06, 0.06, 0.02]


def test_holm_leaves_tests_without_a_p_value_out_of_the_family() -> None:
    assert holm([None, 0.01, None, 0.04]) == [None, 0.02, None, 0.04]
    assert holm([]) == []


@given(st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=20))
def test_holm_never_lowers_a_p_value_exceeds_one_or_breaks_the_order(ps: list[float]) -> None:
    adjusted = holm(ps)
    assert all(a is not None and p <= a <= 1.0 for p, a in zip(ps, adjusted, strict=True))
    values = [a for a in adjusted if a is not None]
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    ranked = [values[i] for i in order]
    assert all(a <= b for a, b in itertools.pairwise(ranked))


def test_adjust_covers_only_the_selected_tests() -> None:
    records = [rec(f"i{i}", "joint", 0, i) for i in range(8)] + [
        rec(f"i{i}", "sequential", 0, i + 5) for i in range(8)
    ]
    c = compare(records, "joint", "sequential")
    [adjusted] = adjust([c], include=lambda _c, t: t.metric == "people_moved")
    by = {t.metric: t for t in adjusted.tests}
    assert by["people_moved"].p_holm == by["people_moved"].p_value  # a family of one
    assert by["cancellations"].p_holm is None  # not selected
    assert by["people_moved"].wins == 8


def test_limit_counts_per_method() -> None:
    records = [
        rec("a", "joint", 0, 1, limit_hit=True, start_unimproved=False),
        rec("b", "joint", 0, 1, limit_hit=True, start_unimproved=True),
        rec("c", "joint", 0, 1),
        rec("a", "greedy", 0, 1, start_unimproved=True),
    ]
    assert limit_counts(records, "joint") == (2, 1, 3)
    assert limit_counts(records, "greedy") == (0, 1, 1)


def test_the_report_separates_primary_from_secondary_and_shows_counts_and_wall_time() -> None:
    records = []
    for i in range(10):
        records += [
            rec(f"i{i}", "joint", 0, i),
            rec(f"i{i}", "sequential", 0, i + 3, limit_hit=True),
            rec(f"i{i}", "greedy", 1, i + 9, start_unimproved=True),
        ]
    report = format_report(records)
    assert "**Primary: joint against sequential" in report
    primary = report.split("**Primary:")[1].split("**Secondary:")[0]
    assert "cancellations | people_moved |" in primary and "delay" not in primary
    secondary = report.split("**Secondary:")[1]
    assert "(primary)" in secondary  # C and P against sequential are not in the family
    assert "Holm p=" in report and "wins 100%" in report
    assert "10 of 10" in report  # sequential stopped at a limit on every run
    assert "wall time total" in report and "stage seconds (tier)" in report
    assert "Methods are given equal optimisation seconds per size tier" in report


def test_a_no_plan_run_is_not_counted_as_unimproved() -> None:
    bad = replace(rec("a", "joint", 0, 1), status=NO_PLAN, values=None, limit_hit=True)
    assert limit_counts([bad], "joint") == (1, 0, 1)
