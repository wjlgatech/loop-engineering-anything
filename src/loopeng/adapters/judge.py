"""CLI-Judge adapter (U5, R2/R3).

Runs ``cli-judge`` against a generated tool and parses ``report.json`` into a
normalized ``Verdict``. The strict safety derivation (KTD5/R3) is the load-
bearing part: ``safety_ok`` is False whenever the safety gate failed OR the
grade was capped at C by the gate.

Open item (doc-review F-4): the exact field that distinguishes a safety-gate cap
from an honestly-earned grade must be pinned against a real ``report.json``.
``derive_safety_ok`` centralizes that logic and recognizes several plausible
encodings; ``strict_unknown`` lets a caller fail closed when no safety signal is
present at all (recommended for autonomous runs).
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import Verdict
from .safety import ProcResult, run_tool


def derive_safety_ok(data: dict, dims: dict, *, strict_unknown: bool = False) -> bool:
    """Strictly derive the safety-gate signal from a parsed report.

    Recognized encodings, in priority order:
      1. explicit boolean flags: ``safety_gate_failed`` / ``safety_capped``
      2. a ``safety`` dimension object carrying ``passed``
      3. no safety signal at all -> ``not strict_unknown`` (fail closed when
         ``strict_unknown`` is set; otherwise assume OK and rely on (1)/(2)).
    """
    if "safety_gate_failed" in data:
        return not bool(data["safety_gate_failed"])
    if "safety_capped" in data:
        return not bool(data["safety_capped"])
    safety = data.get("dimensions", data.get("dims", {})).get("safety")
    if isinstance(safety, dict) and "passed" in safety:
        return bool(safety["passed"])
    return not strict_unknown


def parse_report(data: dict, *, strict_unknown: bool = False) -> Verdict:
    grade = (data.get("grade") or data.get("final_grade") or "").strip().upper()
    score = float(data.get("score", data.get("total", 0)) or 0)

    dims_raw = data.get("dimensions") or data.get("dims") or {}
    dims: dict[str, float] = {}
    for name, val in dims_raw.items():
        dims[name] = float(val["score"]) if isinstance(val, dict) else float(val)

    safety_ok = derive_safety_ok(data, dims, strict_unknown=strict_unknown)
    failing = data.get("failing_fixtures") or data.get("failures") or []
    return Verdict(grade=grade, score=score, dims=dims, safety_ok=safety_ok, failing_fixtures=list(failing))


class CLIJudge:
    """Implements the ``Judge`` protocol by shelling out to ``cli-judge``."""

    def __init__(
        self,
        adapter_path: str,
        *,
        executable: str = "cli-judge",
        suite: str = "full",
        timeout: float = 30 * 60,
        strict_unknown: bool = False,
    ):
        self.adapter_path = adapter_path
        self.executable = executable
        self.suite = suite
        self.timeout = timeout
        self.strict_unknown = strict_unknown

    def _build_command(self) -> list[str]:
        # DOCUMENTED SURFACE: cli-judge run --adapter <x> --suite full
        return [self.executable, "run", "--adapter", self.adapter_path, "--suite", self.suite]

    def judge(self, tool_path: str) -> Verdict:
        result: ProcResult = run_tool(self._build_command(), cwd=tool_path, timeout=self.timeout)
        report = Path(tool_path) / "report.json"
        if not report.exists():
            # No report -> cannot certify safety. Fail closed (KTD5): an absent
            # verdict must not be read as "safe".
            return Verdict(grade="F", score=0.0, dims={}, safety_ok=False,
                           failing_fixtures=["cli-judge produced no report.json"])
        try:
            data = json.loads(report.read_text())
        except (json.JSONDecodeError, OSError):
            return Verdict(grade="F", score=0.0, dims={}, safety_ok=False,
                           failing_fixtures=["report.json was malformed"])
        return parse_report(data, strict_unknown=self.strict_unknown)
