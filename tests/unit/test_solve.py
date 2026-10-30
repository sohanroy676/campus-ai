import pytest
from builders import at, evolve, make_activity, make_problem
from ortools.sat.python import cp_model

from smartcampus.baselines.greedy import greedy
from smartcampus.domain.entities import Cohort, Fault
from smartcampus.domain.plan import Assignment, EquipmentMove, Plan
from smartcampus.domain.problem import RecoveryProblem
from smartcampus.domain.time import Interval
from smartcampus.rules.base import RuleId
from smartcampus.rules.validator import validate
from smartcampus.solver.explain import explain_infeasibility
from smartcampus.solver.objective import StageValues, evaluate
from smartcampus.solver.solve import (
    STAGE_NAMES,
    InfeasibleInputError,
    NoSolutionError,
    SolveResult,
    SolverSettings,
    StageStatus,
    solve,
)

FAST = SolverSettings(stage_seconds=(5, 5, 5, 5, 5, 5))
TUE_10 = at(1, 10)
WHOLE_DAY = Interval(start=at(1, 8), end=at(1, 18))


def closed(*room_ids: str, interval: Interval = WHOLE_DAY) -> tuple[Fault, ...]:
    return tuple(Fault(id=f"fault-{r}", room_id=r, kind="ac", interval=interval) for r in room_ids)


def placement(result_plan_assignments: object, activity_id: str) -> tuple[str, int]:
    [a] = [a for a in result_plan_assignments if a.activity_id == activity_id]  # type: ignore[attr-defined]
    return a.room_id, a.start_min


def assert_moved_to(result: SolveResult, room: str, original_start: int = TUE_10) -> None:
    """Room is fixed by the objective; the start-shift stage keeps the original start."""
    assert placement(result.plan.assignments, "act1") == (room, original_start)


def test_nothing_disrupted_keeps_every_class_where_it_was() -> None:
    result = solve(make_problem(), FAST)
    assert placement(result.plan.assignments, "act1") == ("A1", TUE_10)
    assert result.values == StageValues(0, 0, 0, 0, 0, 0)
    assert [s.name for s in result.stages] == list(STAGE_NAMES)
    assert all(s.status is StageStatus.OPTIMAL for s in result.stages)
    assert validate(make_problem(), result.plan) == []


def test_a_fault_moves_the_class_at_the_lowest_stage_cost() -> None:
    problem = evolve(
        make_problem(), faults=closed("A1", interval=Interval(start=TUE_10, end=at(1, 12)))
    )
    result = solve(problem, FAST)
    # Every way to avoid the fault is one change (26 people) with no delay. The start-shift stage
    # comes before the room tie-break, so A2 at the original time beats A1 an hour earlier.
    assert_moved_to(result, "A2")
    assert result.values == StageValues(0, 26, 0, 0, 0, 1)


def test_when_the_whole_morning_is_lost_the_class_changes_room_instead() -> None:
    morning = Interval(start=at(1, 8), end=at(1, 12))
    problem = evolve(make_problem(), faults=closed("A1", interval=morning))
    result = solve(problem, FAST)
    # A1 reopens at 12:00 (delay 120); A2 is free now (no delay) and in the same building.
    assert_moved_to(result, "A2")
    assert result.values == StageValues(0, 26, 0, 0, 0, 1)


def test_avoiding_a_cancellation_beats_any_amount_of_disruption() -> None:
    # 55 students and a closed A1: moving costs 56 people-moved, cancelling costs 0 there.
    # A weighted sum could prefer cancelling; the lexicographic order never does.
    problem = evolve(
        make_problem(),
        cohorts=(Cohort(id="c1", size=55), Cohort(id="c2", size=20)),
        faults=closed("A1"),
    )
    result = solve(problem, FAST)
    assert result.plan.cancelled == frozenset()
    assert_moved_to(result, "A2")
    assert result.values.cancellations == 0
    assert result.values.people_moved == 56


def test_a_class_that_fits_nowhere_is_cancelled() -> None:
    problem = evolve(make_problem(), faults=closed("A1", "A2", "B1"))
    result = solve(problem, FAST)
    assert result.plan.cancelled == frozenset({"act1"})
    assert result.plan.assignments == ()
    assert result.values == StageValues(1, 0, 0, 0, 0, 0)


def test_another_building_is_used_only_when_nothing_else_fits() -> None:
    problem = evolve(
        make_problem(),
        cohorts=(Cohort(id="c1", size=35), Cohort(id="c2", size=20)),
        faults=closed("A1", "A2"),
    )
    result = solve(problem, FAST)
    assert_moved_to(result, "B1")
    assert result.values == StageValues(0, 36, 0, 0, 0, 1002)  # 1000 for the building + rank 2


def test_delay_is_chosen_over_a_cancellation_when_the_room_reopens() -> None:
    reopens = Interval(start=at(1, 8), end=at(1, 12))
    problem = evolve(make_problem(), faults=closed("A1", "A2", "B1", interval=reopens))
    result = solve(problem, FAST)
    assert result.values.cancellations == 0
    assert placement(result.plan.assignments, "act1") == ("A1", at(1, 12))  # earliest, first room
    assert result.values.delay == 120


def test_equipment_follows_the_class_to_the_new_room() -> None:
    problem = evolve(
        make_problem(activities=(make_activity(required_equipment={"gpu": 3}),)),
        faults=closed("A1"),  # the lab with all four gpus is closed
    )
    result = solve(problem, FAST)
    assert_moved_to(result, "A2")
    [move] = result.plan.moves
    assert (move.pool_id, move.activity_id, move.units) == ("gpu", "act1", 3)
    assert move.end_min <= placement(result.plan.assignments, "act1")[1]  # before class
    assert result.values.cost == 3 * 5 + 15
    assert validate(problem, result.plan) == []


def test_stage_values_are_the_real_score_of_the_plan() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    result = solve(problem, FAST)
    assert result.values == evaluate(problem, result.plan)
    assert [s.value for s in result.stages] == list(
        (
            result.values.cancellations,
            result.values.people_moved,
            result.values.delay,
            result.values.cost,
            result.values.start_shift,
            result.values.tie_break,
        )
    )


def test_solving_twice_gives_the_same_plan() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    first, second = solve(problem, FAST), solve(problem, FAST)
    assert (first.plan, first.values) == (second.plan, second.values)


def test_nothing_to_recover_gives_an_empty_plan() -> None:
    problem = evolve(make_problem(), movable_activity_ids=frozenset())
    result = solve(problem, FAST)
    assert result.plan.assignments == () and result.plan.cancelled == frozenset()
    assert result.values == StageValues(0, 0, 0, 0, 0, 0)


def test_a_short_time_limit_still_returns_a_valid_plan() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    result = solve(problem, SolverSettings(stage_seconds=(0.5,) * 6))
    assert validate(problem, result.plan) == []


def two_unaffected_classes_in_one_room() -> RecoveryProblem:
    return make_problem(
        activities=(
            make_activity(),
            make_activity(
                id="fixed1", cohort_id="c2", faculty_ids=("f2",), room_id="A2", start_min=at(1, 12)
            ),
            make_activity(
                id="fixed2", cohort_id="c1", faculty_ids=("f1",), room_id="A2", start_min=at(1, 12)
            ),
        ),
    )


def test_unsolvable_input_names_the_broken_rule() -> None:
    problem = two_unaffected_classes_in_one_room()
    with pytest.raises(InfeasibleInputError) as excinfo:
        solve(problem, FAST)
    assert excinfo.value.rules == {RuleId.R2}
    assert "R2" in str(excinfo.value)


def test_explaining_a_solvable_problem_gives_no_rules() -> None:
    assert explain_infeasibility(make_problem()) == frozenset()
    assert explain_infeasibility(two_unaffected_classes_in_one_room()) == {RuleId.R2}


def fake_status(monkeypatch: pytest.MonkeyPatch, statuses_after_first: int) -> None:
    """Report UNKNOWN (no solution in time) after `statuses_after_first` genuine solves."""
    real_solve = cp_model.CpSolver.solve
    calls = {"n": 0}

    def solve_with_timeouts(self: cp_model.CpSolver, model: cp_model.CpModel) -> int:
        calls["n"] += 1
        if calls["n"] > statuses_after_first:
            return int(cp_model.UNKNOWN)
        return int(real_solve(self, model))

    monkeypatch.setattr(cp_model.CpSolver, "solve", solve_with_timeouts)


def test_no_solution_in_the_first_stage_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_status(monkeypatch, statuses_after_first=0)
    with pytest.raises(NoSolutionError):
        solve(make_problem(), FAST)


def test_a_later_stage_that_times_out_keeps_the_plan_so_far(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    expected = solve(problem, FAST)
    fake_status(monkeypatch, statuses_after_first=2)  # C and P solved; D, K, S, T "time out"
    result = solve(problem, FAST)
    assert [s.status for s in result.stages[2:]] == [StageStatus.TIME_LIMIT] * 4
    assert validate(problem, result.plan) == []
    assert result.values.cancellations == expected.values.cancellations
    assert result.values.people_moved == expected.values.people_moved


def disrupted_with_gpus() -> RecoveryProblem:
    return evolve(
        make_problem(activities=(make_activity(required_equipment={"gpu": 3}),)),
        faults=closed("A1"),
    )


def test_a_greedy_hint_does_not_change_the_optimum() -> None:
    for problem in (evolve(make_problem(), faults=closed("A1")), disrupted_with_gpus()):
        start = greedy(problem)
        hinted = solve(problem, FAST, hint=start)
        plain = solve(problem, FAST)
        assert hinted.values == plain.values
        assert hinted.plan == plain.plan


def test_a_bad_hint_only_costs_search_time_not_the_answer() -> None:
    problem = disrupted_with_gpus()
    worst = Plan(based_on_version=0, assignments=(), cancelled=frozenset({"act1"}), moves=())
    assert solve(problem, FAST, hint=worst).values == solve(problem, FAST).values


def test_a_hint_naming_things_the_model_lacks_is_ignored() -> None:
    problem = evolve(make_problem(), faults=closed("A1"))
    junk = Plan(
        based_on_version=0,
        assignments=(Assignment(activity_id="act1", room_id="nowhere", start_min=TUE_10),),
        cancelled=frozenset({"ghost"}),
        moves=(
            EquipmentMove(pool_id="none", activity_id="ghost", units=1, start_min=0, end_min=20),
        ),
    )
    assert solve(problem, FAST, hint=junk).values == solve(problem, FAST).values
