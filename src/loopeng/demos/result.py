"""Demo result fixture: load + schema-validate (U1).

A result carries explicit ``source`` provenance (``illustrative`` vs
``live_verified``) so the showcase can never present a hand-authored trajectory
as a verified engine run (KTD2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

from .manifest import ManifestError

_RESULT_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "demos" / "RESULT_SCHEMA.json"


@dataclass
class Result:
    demo_id: str
    source: str  # "illustrative" | "live_verified"
    grade_trajectory: list[str]
    final_grade: str
    convergence_status: str
    report_ref: str | None = None
    recorded_at: str | None = None
    engine_version: str | None = None

    @property
    def verified(self) -> bool:
        return self.source == "live_verified"


def from_dict(data: dict) -> Result:
    try:
        jsonschema.validate(data, json.loads(_RESULT_SCHEMA_PATH.read_text()))
    except jsonschema.ValidationError as exc:
        field_path = ".".join(str(p) for p in exc.absolute_path) or "(root)"
        raise ManifestError(f"result fixture invalid at {field_path}: {exc.message}") from exc
    return Result(
        demo_id=data["demo_id"],
        source=data["source"],
        grade_trajectory=list(data["grade_trajectory"]),
        final_grade=data["final_grade"],
        convergence_status=data["convergence_status"],
        report_ref=data.get("report_ref"),
        recorded_at=data.get("recorded_at"),
        engine_version=data.get("engine_version"),
    )


def load_result(path: str | Path) -> Result:
    return from_dict(json.loads(Path(path).read_text()))
