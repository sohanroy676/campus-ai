"""Text summary and JSON report of one run."""

import json
from pathlib import Path
from typing import Any

from smartcampus.coordinator.run import RunResult
from smartcampus.domain.time import MINUTES_PER_DAY

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
STAGE_LABELS = (
    ("cancellations", "cancellations"),
    ("people_moved", "people moved"),
    ("delay", "delay (min)"),
    ("cost", "cost"),
    ("start_shift", "start shift (min)"),
    ("tie_break", "tie-break"),
)


def format_minute(minute: int) -> str:
    """Minutes from Monday 00:00 as e.g. `Tue 10:00`."""
    day, in_day = divmod(minute, MINUTES_PER_DAY)
    return f"{DAY_NAMES[day % 7]} {in_day // 60:02d}:{in_day % 60:02d}"


def format_summary(result: RunResult, scenario: Path, db: Path) -> str:
    problem, plan = result.problem, result.plan
    window = problem.window
    placed = {a.activity_id: a for a in plan.assignments}
    lines = [
        f"Scenario:   {scenario}",
        f"Method:     {result.method.value}",
        f"Disruption: {len(problem.faults)} fault(s), {len(problem.holds)} hold(s); "
        f"recovery window {format_minute(window.start)} to {format_minute(window.end)}; "
        f"{len(problem.movable_activity_ids)} class(es) to recover",
        f"Plan (built on version {plan.based_on_version}, "
        f"applied as event {result.log_version - 1}):",
    ]
    for activity in sorted(
        (problem.activity(a) for a in problem.movable_activity_ids), key=lambda a: a.id
    ):
        before = f"{activity.room_id} {format_minute(activity.start_min)}"
        if activity.id in plan.cancelled:
            lines.append(f"  {activity.id}: CANCELLED (was {before})")
        else:
            a = placed[activity.id]  # a valid plan assigns or cancels every affected class
            if (a.room_id, a.start_min) == (activity.room_id, activity.start_min):
                lines.append(f"  {activity.id}: unchanged ({before})")
            else:
                after = f"{a.room_id} {format_minute(a.start_min)}"
                lines.append(f"  {activity.id}: {before} -> {after}")
    for move in plan.moves:
        lines.append(
            f"  equipment: {move.units} x {move.pool_id} -> {move.activity_id}, "
            f"carried {format_minute(move.start_min)} to {format_minute(move.end_min)}"
        )
    score = " | ".join(f"{label} {getattr(result.values, name)}" for name, label in STAGE_LABELS)
    lines += [
        f"Score (lexicographic, lower is better): {score}",
        "Hard rules R1-R8: all satisfied (independent re-check)",
        f"Event log: {result.log_version} event(s) in {db}",
    ]
    return "\n".join(lines)


def report_dict(result: RunResult, scenario: Path) -> dict[str, Any]:
    """Everything needed to repeat the run, and its outcome (no wall-clock times)."""
    plan = result.plan.model_dump(mode="json")
    plan["cancelled"] = sorted(plan["cancelled"])
    settings = result.settings
    return {
        "scenario": scenario.as_posix(),
        "method": result.method.value,
        "solver": None
        if settings is None
        else {
            "stage_seconds": list(settings.stage_seconds),
            "num_workers": settings.num_workers,
            "random_seed": settings.random_seed,
        },
        "stage_values": {name: getattr(result.values, name) for name, _ in STAGE_LABELS},
        "stage_status": {s.name: s.status.value for s in result.stages},
        "plan": plan,
        "log_version": result.log_version,
    }


def write_report(result: RunResult, scenario: Path, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report_dict(result, scenario), indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
