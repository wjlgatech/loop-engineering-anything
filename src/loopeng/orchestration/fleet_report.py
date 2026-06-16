"""Fleet research report (plan-006 U5).

Aggregates per-item lifecycle + outcome into a fleet-level view. Kept here in
``orchestration/`` (not folded into ``autonomous/report.py``) so the per-run
report stays the untouched building block — a fleet report is a *composition* of
per-item run state, not a change to single-run reporting.
"""

from __future__ import annotations

import json

from ..memory.fleet_state import FleetItemStatus
from ..memory.store import MemoryStore


def build_fleet_report(store: MemoryStore, fleet_id: int) -> dict | None:
    """A JSON-able fleet report: run status + per-item lifecycle/grade + the
    escalation list. ``None`` when the fleet id is unknown."""
    fleet = store.get_fleet(fleet_id)
    if fleet is None:
        return None
    items = store.fleet_items(fleet_id)
    return {
        "fleet_id": fleet_id,
        "goal": fleet.goal,
        "status": fleet.status.value,
        "started": fleet.started,
        "finished": fleet.finished,
        "items": [
            {
                "key": i.key,
                "status": i.status.value,
                "depends_on": i.depends_on,
                "run_id": i.run_id,
                "grade": (i.outcome or {}).get("grade"),
                "gate_reason": (i.outcome or {}).get("gate_reason"),
            }
            for i in items
        ],
        "escalations": [i.key for i in items if i.status is FleetItemStatus.ESCALATED],
    }


def render_fleet_report(report: dict, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report, indent=2)
    lines = [
        f"Fleet #{report['fleet_id']}  status={report['status']}  goal={report['goal'] or '-'}",
    ]
    for it in report["items"]:
        dep = f"  deps={','.join(it['depends_on'])}" if it["depends_on"] else ""
        grade = f"  grade={it['grade']}" if it["grade"] else ""
        lines.append(f"  - {it['key']:<16} {it['status']}{grade}{dep}")
    if report["escalations"]:
        lines.append(f"  escalations: {', '.join(report['escalations'])}")
    return "\n".join(lines)
