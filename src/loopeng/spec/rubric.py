"""Deterministic rubric for grading a spec/plan document (plan 2026-06-21 U7).

The spec analogue of CLI-Judge's `report.json`: a structurally-decidable score over
five dimensions, with **no semantic NLP** so repeated grading of the same spec returns
identical scores (a safe single-run control signal, like CLI-Judge's 0.0 variance).
Dimensions deliberately reward measurable structure, not prose volume:

  completeness   problem-frame + requirements + units + per-unit test scenarios present
  testability    acceptance/test scenarios present, and the share of units that have them
  consistency    cross-reference resolution -- every U#/R# referenced is defined; a
                 deterministic proxy for "terminology drift", NOT contradiction detection
  scope          a Scope section exists and units trace to requirements (no orphan units)
  grounding      concrete file-path / decision citations are present

Each dimension scores 0..20 -> total 0..100 -> letter grade. `failing_fixtures` names
the concrete gaps so the spec-refiner's brief can target them.
"""

from __future__ import annotations

import re

from ..util.sanitize import sanitize_text

_DIM_MAX = 20
_GRADE_BANDS = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]

_H = lambda kw: re.compile(rf"(?im)^#{{1,6}}\s*{kw}")
_RE_PROBLEM = _H(r"(problem frame|summary|overview)\b")
_RE_REQS = _H(r"requirements\b")
_RE_SCOPE = _H(r"scope\b")
_RE_UNIT_DEF = re.compile(r"(?im)^#{1,6}\s*U(\d+)\b")          # "### U1. ..."
_RE_UNIT_REF = re.compile(r"\bU(\d+)\b")
_RE_R_DEF = re.compile(r"\bR(\d+)\b\s*[—:\-]")                  # "R1 — ..." / "R1:"
_RE_R_REF = re.compile(r"\bR(\d+)\b")
_RE_TESTS = re.compile(r"(?i)test scenario|acceptance|verif")
_RE_CITATION = re.compile(r"`[^`]*[./][^`]*`|\b[\w.\-]+/[\w./\-]+\b")


def _grade_for(score: float) -> str:
    for cutoff, letter in _GRADE_BANDS:
        if score >= cutoff:
            return letter
    return "F"


def score_spec(text: str) -> dict:
    """Score a spec document. Returns ``{grade, score, dims, failing_fixtures, feedback}``.
    Fail-closed: empty / non-string input -> grade F, score 0 (never raises)."""
    if not isinstance(text, str) or not text.strip():
        return {
            "grade": "F", "score": 0.0,
            "dims": {"completeness": 0, "testability": 0, "consistency": 0, "scope": 0, "grounding": 0},
            "failing_fixtures": ["empty_or_unreadable_spec"],
            "feedback": "spec is empty or unreadable",
        }

    fixtures: list[str] = []
    unit_ids = {int(m) for m in _RE_UNIT_DEF.findall(text)}
    # Per-unit blocks for the "has test scenarios" check (split on unit headings).
    unit_blocks = re.split(r"(?im)^#{1,6}\s*U\d+\b", text)[1:]

    # --- completeness (20) ---
    comp = 0
    if _RE_PROBLEM.search(text):
        comp += 5
    else:
        fixtures.append("missing:problem_frame")
    if _RE_REQS.search(text) and _RE_R_REF.search(text):
        comp += 5
    else:
        fixtures.append("missing:requirements")
    if unit_ids:
        comp += 5
    else:
        fixtures.append("missing:implementation_units")
    units_with_tests = sum(1 for b in unit_blocks if _RE_TESTS.search(b))
    if unit_blocks and units_with_tests == len(unit_blocks):
        comp += 5
    elif unit_blocks:
        fixtures.append("units_without_test_scenarios")

    # --- testability (20) ---
    test = 0
    if _RE_TESTS.search(text):
        test += 10
    else:
        fixtures.append("missing:test_scenarios")
    if unit_blocks:
        test += round(10 * units_with_tests / len(unit_blocks))

    # --- consistency (20): cross-reference resolution (deterministic proxy) ---
    cons = 20
    dangling_u = {u for u in (int(m) for m in _RE_UNIT_REF.findall(text)) if u not in unit_ids}
    r_defs = {int(m) for m in _RE_R_DEF.findall(text)}
    dangling_r = {r for r in (int(m) for m in _RE_R_REF.findall(text)) if r not in r_defs}
    if dangling_u:
        cons -= 10
        fixtures.append("dangling_unit_refs:" + ",".join(f"U{u}" for u in sorted(dangling_u)))
    if dangling_r and r_defs:  # only penalize when some R defs exist (else "requirements" already flagged)
        cons -= 10
        fixtures.append("dangling_requirement_refs:" + ",".join(f"R{r}" for r in sorted(dangling_r)))

    # --- scope-boundedness (20) ---
    scope = 0
    if _RE_SCOPE.search(text):
        scope += 10
    else:
        fixtures.append("missing:scope_boundaries")
    if unit_ids and _RE_R_REF.search(text):  # units exist and requirements are referenced -> traceable
        scope += 10
    elif unit_ids:
        fixtures.append("units_not_traced_to_requirements")

    # --- grounding (20) ---
    ground = 20 if _RE_CITATION.search(text) else 0
    if not ground:
        fixtures.append("missing:grounding_citations")

    dims = {"completeness": comp, "testability": test, "consistency": cons, "scope": scope, "grounding": ground}
    total = float(sum(dims.values()))
    weakest = sorted(dims.items(), key=lambda kv: kv[1])[:2]
    feedback = sanitize_text(
        "weakest dimensions: " + "; ".join(f"{n} {v}/{_DIM_MAX}" for n, v in weakest)
    )
    return {"grade": _grade_for(total), "score": total, "dims": dims,
            "failing_fixtures": fixtures, "feedback": feedback}
