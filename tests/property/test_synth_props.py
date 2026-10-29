"""Any seed and parameters give a scenario that loads, repeats and can always be recovered."""

from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from smartcampus.domain.plan import Plan
from smartcampus.generator.scenario import dump_scenario, load_scenario
from smartcampus.generator.synth import SEVERITIES, generate_scenario
from smartcampus.rules.validator import validate

small_parameters = st.tuples(
    st.sampled_from([10, 50, 75, 90]), st.sampled_from(SEVERITIES), st.integers(0, 10_000)
)


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(params=small_parameters)
def test_a_generated_scenario_repeats_and_round_trips(
    params: tuple[int, str, int], tmp_path: Path
) -> None:
    load, severity, seed = params
    problem = generate_scenario("small", load, severity, seed)
    assert dump_scenario(generate_scenario("small", load, severity, seed)) == dump_scenario(problem)
    path = tmp_path / "s.json"
    path.write_text(dump_scenario(problem), encoding="utf-8", newline="\n")
    assert load_scenario(path) == problem


@settings(max_examples=25)
@given(small_parameters)
def test_the_fixed_classes_obey_the_rules_so_a_plan_exists(params: tuple[int, str, int]) -> None:
    load, severity, seed = params
    problem = generate_scenario("small", load, severity, seed)
    cancel_all = Plan(based_on_version=0, assignments=(), cancelled=problem.movable_activity_ids)
    assert validate(problem, cancel_all) == []


@settings(max_examples=25)
@given(small_parameters)
def test_disruptions_start_in_the_teaching_week_after_plan_time(
    params: tuple[int, str, int],
) -> None:
    load, severity, seed = params
    problem = generate_scenario("small", load, severity, seed)
    for interval in [f.interval for f in problem.faults] + [h.interval for h in problem.holds]:
        assert interval.start >= problem.plan_time_min
    assert problem.movable_activity_ids <= {a.id for a in problem.activities}
