"""Translate a Verdict into a focused refactor brief (U6).

Targets the lowest-scoring dimensions plus their failing fixtures -- not the
whole report -- so the refinement engine works on what actually moves the grade.
"""

from __future__ import annotations

from ..adapters.base import RefactorBrief, Verdict


def build_refactor_brief(verdict: Verdict, goal: str = "") -> RefactorBrief:
    # Rank dimensions lowest-score-first; those are where the grade is bleeding.
    ranked = [name for name, _ in sorted(verdict.dims.items(), key=lambda kv: kv[1])]
    objective = goal or (
        f"Raise the grade from {verdict.grade} by fixing the lowest-scoring "
        f"dimensions first."
    )
    return RefactorBrief(
        goal=objective,
        target_dimensions=ranked,
        failing_fixtures=list(verdict.failing_fixtures),
    )
