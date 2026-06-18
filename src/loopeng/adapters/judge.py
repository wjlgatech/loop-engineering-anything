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
import os
from dataclasses import dataclass
from pathlib import Path

from .base import GenerateResult, Judge, Verdict
from .safety import ProcResult, run_tool, within_workspace


class JudgeAdapterError(RuntimeError):
    """No usable CLI-Judge adapter could be resolved for a target (fail-closed).

    Raised on a missing adapter, a wrong explicit override, or — critically — an
    adapter that resolves *inside* the maker's write tree or escapes the operator
    registry. The referee must be immutable to the maker (KTD3), so an in-jail
    adapter is rejected rather than silently trusted.
    """


def resolve_judge_adapter(
    gen: GenerateResult,
    *,
    override: str | None = None,
    registry_dir: str | None = None,
) -> str:
    """Resolve the CLI-Judge adapter path for a generated tool, fail-closed.

    Precedence (deterministic):
      1. ``override`` (operator-supplied ``--judge-adapter``) — must exist.
      2. an operator-controlled ``registry_dir`` entry named by the tool's
         manifest (``judge_adapter`` path/basename, or ``<id>.py``).

    Every resolved path must (a) exist and (b) live OUTSIDE ``gen.tool_path`` —
    the maker's write jail — or ``JudgeAdapterError`` is raised. A manifest-named
    path that escapes ``registry_dir`` is rejected (path-escape guard). When
    nothing resolves, the error names the ``--judge-adapter`` escape hatch."""
    tool_path = gen.tool_path

    def _out_of_jail(path: str) -> str:
        ap = os.path.abspath(path)
        if within_workspace(ap, tool_path):
            raise JudgeAdapterError(
                f"refusing a CLI-Judge adapter inside the generated tool ({ap}): the "
                f"referee must be immutable to the maker. Pass --judge-adapter to a "
                f"path outside {tool_path}."
            )
        return ap

    # 1. Explicit override — highest trust, but still must exist and be out-of-jail.
    if override:
        if not os.path.exists(override):
            raise JudgeAdapterError(f"--judge-adapter path does not exist: {override}")
        return _out_of_jail(override)

    # 2. Operator-controlled registry, addressed by the tool's manifest.
    if registry_dir:
        reg = os.path.abspath(registry_dir)
        named = gen.manifest.get("judge_adapter")
        if not named and gen.manifest.get("id"):
            named = f"{gen.manifest['id']}.py"
        if named:
            cand = os.path.abspath(os.path.join(reg, named))
            # Path-escape guard: a manifest must not point outside the registry.
            if not within_workspace(cand, reg):
                raise JudgeAdapterError(
                    f"manifest judge adapter escapes the operator registry: {named!r}"
                )
            if os.path.exists(cand):
                return _out_of_jail(cand)

    raise JudgeAdapterError(
        f"no CLI-Judge adapter found for this tool; pass --judge-adapter PATH "
        f"(a path outside the generated tool at {tool_path})"
    )


def derive_safety_ok(data: dict, dims: dict, *, strict_unknown: bool = False) -> bool:
    """Strictly derive the safety-gate signal from a parsed report.

    Recognized encodings, in priority order:
      1. ``safety_blocker`` -- the REAL CLI-Judge field (pinned against a live
         ``report.json``): a true blocker caps the grade and means not-shippable.
      2. explicit boolean flags: ``safety_gate_failed`` / ``safety_capped``
      3. a ``safety`` dimension object carrying ``passed``
      4. no safety signal at all -> ``not strict_unknown`` (fail closed when
         ``strict_unknown`` is set; otherwise assume OK and rely on (1)-(3)).
    """
    if "safety_blocker" in data:
        return not bool(data["safety_blocker"])
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

    # Dimensions: CLI-Judge keys them D1..D5 with points/max_points; earlier
    # fixtures used name->score. Accept both.
    dims_raw = data.get("dimensions") or data.get("dims") or {}
    dims: dict[str, float] = {}
    for name, val in dims_raw.items():
        if isinstance(val, dict):
            dims[name] = float(val.get("score", val.get("points", 0)))
        else:
            dims[name] = float(val)

    safety_ok = derive_safety_ok(data, dims, strict_unknown=strict_unknown)

    # Failing fixtures: explicit list if present, else derive from tasks that
    # lost points (the real CLI-Judge shape).
    failing = data.get("failing_fixtures") or data.get("failures")
    if failing is None:
        failing = [
            t.get("id")
            for t in data.get("tasks", [])
            if t.get("points", 0) < t.get("max_points", 0)
        ]
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

    def _build_command(self, out_dir: str) -> list[str]:
        # PINNED against a live cli-judge: report.json is written to --out, and
        # suites are bundled (resolve from any cwd).
        return [
            self.executable, "run",
            "--adapter", self.adapter_path,
            "--suite", self.suite,
            "--out", out_dir,
        ]

    def judge(self, tool_path: str) -> Verdict:
        out_dir = os.path.join(tool_path, ".cli-judge")
        os.makedirs(out_dir, exist_ok=True)
        result: ProcResult = run_tool(self._build_command(out_dir), cwd=None, timeout=self.timeout)
        report = Path(out_dir) / "report.json"
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


@dataclass(frozen=True)
class VarianceReport:
    """Result of re-judging an unchanged tool K times (P0 #2 spike).

    If ``grade_stable`` is False, single-run grade deltas are unsafe as a control
    signal -- set ``Budget.min_score_gain`` to at least ``recommended_min_score_gain``
    so the loop only accepts gains that clear the observed jitter.
    """

    grades: list
    scores: list
    grade_stable: bool
    score_spread: float
    recommended_min_score_gain: float


def probe_grade_variance(judge: Judge, tool_path: str, k: int = 5) -> VarianceReport:
    """Re-judge an unchanged tool ``k`` times and report grade/score variance.

    This is the multi-seed variance probe a continuous-score domain needs (U10):
    a stochastic referee (e.g. a sim averaging rollouts) re-seeds on each
    ``judge`` call, so the score spread across ``k`` calls measures referee
    noise. A non-deterministic referee MUST run with ``Budget.min_score_gain``
    set to at least ``recommended_min_score_gain`` (> 0) so the loop does not
    accept sub-noise jitter as a real gain.
    """
    if k < 2:
        raise ValueError("k must be >= 2 to measure variance")
    verdicts = [judge.judge(tool_path) for _ in range(k)]
    grades = [v.grade for v in verdicts]
    scores = [v.score for v in verdicts]
    spread = (max(scores) - min(scores)) if scores else 0.0
    return VarianceReport(
        grades=grades,
        scores=scores,
        grade_stable=len(set(grades)) == 1,
        score_spread=spread,
        recommended_min_score_gain=spread,
    )
