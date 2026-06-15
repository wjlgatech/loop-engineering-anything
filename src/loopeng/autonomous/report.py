"""Research report renderer (U8, R9).

Renders a run's grade trajectory, compounded learnings, and final status from
the memory store, in human (Markdown) or ``--json`` form. The report includes
only metadata (grades, dimensions, learning summaries) -- never raw diff content
or log fields that could carry credentials or API responses (security finding).
"""

from __future__ import annotations

import json

from ..memory.store import MemoryStore


def build_report(store: MemoryStore, run_id: int) -> dict:
    run = store.get_run(run_id)
    if run is None:
        raise ValueError(f"no run with id {run_id}")
    iterations = store.iterations(run_id)
    return {
        "run_id": run.id,
        "target": run.target,
        "lane": run.lane,
        "goal": run.goal,
        "status": run.status,
        "final_grade": run.final_grade,
        "grade_trajectory": [it.grade for it in iterations],
        "iterations": len(iterations),
        "learnings": [
            {"summary": l["summary"], "regression_test_ref": l["regression_test_ref"]}
            for l in store.learnings(run_id)
        ],
    }


def render_report(store: MemoryStore, run_id: int, *, as_json: bool = False) -> str:
    data = build_report(store, run_id)
    if as_json:
        return json.dumps(data, indent=2)

    lines = [
        f"# Research report — run #{data['run_id']}",
        "",
        f"- Target: {data['target']} ({data['lane']} lane)",
        f"- Goal: {data['goal'] or '-'}",
        f"- Status: **{data['status']}**  |  Final grade: **{data['final_grade'] or '-'}**",
        f"- Iterations: {data['iterations']}",
        f"- Grade trajectory: {' -> '.join(data['grade_trajectory']) or '-'}",
        "",
        "## Learnings compounded",
    ]
    if data["learnings"]:
        for l in data["learnings"]:
            ref = f" (regression: {l['regression_test_ref']})" if l["regression_test_ref"] else ""
            lines.append(f"- {l['summary']}{ref}")
    else:
        lines.append("- (none)")
    return "\n".join(lines)
