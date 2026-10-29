# Testing Requirements

After implementing any feature or fix:

1. Check if tests already exist for the changed code.
2. If no tests exist, write tests covering:
    - The main expected behavior (happy path)
    - Edge cases (empty input, null/undefined, boundary values, large inputs)
    - Error/failure paths (invalid input, infeasible models, etc. where relevant)
3. Write tests "as if trying to break the feature" — genuinely adversarial, not just re-confirming the code does what it does.
4. Run the FULL test suite (`uv run pytest`) to catch regressions.
5. If any test fails, debug and fix the root cause before proceeding. Never comment out or delete a failing test to make the suite pass.
6. Only after all tests pass, proceed to the commit workflow.

Framework, location and naming are defined in `memory-bank/tech-stack.md`: `tests/unit/test_<module>.py`, `tests/property/test_<rule>_props.py` (Hypothesis), `tests/golden/test_<scenario>.py`. Follow that convention exactly. Golden/evaluation runs use `num_workers=1`, `random_seed=42`. Coverage target: 85% for `rules/`, `solver/`, `sim/`.

Run slow suites (full eval, large property runs) in the background and watch them with Monitor (see CLAUDE.md), not by polling.
