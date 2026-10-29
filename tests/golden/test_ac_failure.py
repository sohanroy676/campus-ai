"""Golden results for scenarios/dev/ac-failure.json (AI-Lab-01 AC failure, Tue 10:00 to 14:00).

Solver settings are the defaults: num_workers=1, random_seed=42. If a number here changes, the
objective, a rule or the solver changed: decide whether that is intended before updating it.
"""

from pathlib import Path

from builders import at

from smartcampus.coordinator.run import Method, RunResult, run_scenario
from smartcampus.domain.plan import Assignment, EquipmentMove
from smartcampus.generator.scenario import load_scenario
from smartcampus.sim.store import EventStore
from smartcampus.solver.objective import StageValues
from smartcampus.solver.solve import SolverSettings

DEMO = Path(__file__).parents[2] / "scenarios" / "dev" / "ac-failure.json"


def run(method: Method) -> RunResult:
    with EventStore() as store:
        return run_scenario(load_scenario(DEMO), method, store, SolverSettings())


def test_joint_moves_only_the_lab_class_and_borrows_the_gpus_in_time() -> None:
    result = run(Method.JOINT)
    assert result.plan.cancelled == frozenset()
    assert set(result.plan.assignments) == {
        Assignment(activity_id="ml-lab", room_id="AI-Lab-02", start_min=at(1, 9)),
        Assignment(activity_id="net-lab", room_id="AI-Lab-02", start_min=at(1, 10)),
        Assignment(activity_id="data-lecture", room_id="Lec-A1", start_min=at(1, 13)),
    }
    assert result.plan.moves == (
        EquipmentMove(
            pool_id="gpu-01",
            activity_id="ml-lab",
            units=3,
            start_min=at(1, 8, 30),
            end_min=at(1, 9),
        ),
    )
    assert result.values == StageValues(0, 26, 0, 30, 60, 1)


def test_greedy_disturbs_a_second_class_because_it_does_not_look_ahead() -> None:
    result = run(Method.GREEDY)
    assert result.plan.cancelled == frozenset()
    assert set(result.plan.assignments) == {
        Assignment(activity_id="ml-lab", room_id="AI-Lab-02", start_min=at(1, 10)),
        Assignment(activity_id="net-lab", room_id="AI-Lab-02", start_min=at(1, 9)),
        Assignment(activity_id="data-lecture", room_id="Lec-A1", start_min=at(1, 13)),
    }
    assert result.values == StageValues(0, 55, 0, 30, 60, 2)


def test_joint_beats_greedy_on_the_demo() -> None:
    assert run(Method.JOINT).values < run(Method.GREEDY).values
