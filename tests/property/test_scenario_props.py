"""Any valid problem survives a trip through a scenario file, and the file text is stable."""

from hypothesis import given, settings
from pydantic import ValidationError
from strategies import problems

from smartcampus.domain.problem import RecoveryProblem
from smartcampus.generator.scenario import dump_scenario


@settings(max_examples=100)
@given(problems())
def test_dump_then_load_gives_the_same_problem(problem: RecoveryProblem) -> None:
    text = dump_scenario(problem)
    assert RecoveryProblem.model_validate_json(text) == problem


@settings(max_examples=100)
@given(problems())
def test_the_file_text_does_not_depend_on_set_order(problem: RecoveryProblem) -> None:
    text = dump_scenario(problem)
    assert dump_scenario(RecoveryProblem.model_validate_json(text)) == text


@settings(max_examples=50)
@given(problems())
def test_dropping_any_required_key_is_rejected(problem: RecoveryProblem) -> None:
    import json

    data = json.loads(dump_scenario(problem))
    for key in ("campus", "cohorts", "faculty", "activities", "movable_activity_ids", "window"):
        broken = {k: v for k, v in data.items() if k != key}
        try:
            RecoveryProblem.model_validate(broken)
        except ValidationError:
            continue
        raise AssertionError(f"a scenario without {key} was accepted")
