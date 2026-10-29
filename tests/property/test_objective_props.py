"""The CP-SAT stage expressions and the plain-Python reference score must be the same function."""

from dataclasses import astuple

from cp_helpers import fix_plan, solver
from hypothesis import given, settings
from hypothesis import strategies as st
from ortools.sat.python import cp_model
from strategies import SOUND_MODES, plans, problems

from smartcampus.rules.variables import build_variables
from smartcampus.solver.objective import evaluate, stage_expressions


@settings(max_examples=120)
@given(st.data())
def test_expressions_equal_the_reference_score_on_any_plan(data: st.DataObject) -> None:
    problem = data.draw(problems())
    plan = data.draw(plans(problem, modes=SOUND_MODES))
    ctx = build_variables(problem)
    expressions = stage_expressions(ctx)
    assert fix_plan(ctx, plan)
    s = solver()
    assert s.solve(ctx.model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert tuple(s.value(e) for e in expressions) == astuple(evaluate(problem, plan))


@settings(max_examples=60)
@given(st.data())
def test_cancelling_everything_scores_only_the_first_stage(data: st.DataObject) -> None:
    problem = data.draw(problems(all_movable=True))
    plan = data.draw(plans(problem, modes=("cancel",), with_moves=False))
    scored = evaluate(problem, plan)
    assert scored.cancellations == len(problem.movable_activity_ids)
    assert astuple(scored)[1:] == (0, 0, 0, 0)
