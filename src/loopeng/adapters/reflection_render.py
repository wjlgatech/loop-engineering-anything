"""Shared rendering of a ``ReflectionContext`` into a refiner prompt (plan 2026-06-20 U3).

Both refiners render the same trace-driven ASI so the reflective gradient reaches the
model regardless of which refiner runs (KTD2). The LLM refiner passes a ``sanitize``
callable (``_clip``) as defense-in-depth; the ClaudeCodeRefiner relies on the
source-side sanitization of ``judge_feedback`` (U4), consistent with how it already
renders the un-clipped ``recurring_failures`` / ``upstream_outcomes`` fields.
"""

from __future__ import annotations

from typing import Callable

_MAX_PERSISTENT = 5  # cap fixtures rendered so the prompt stays a directive, not a dump


def reflection_lines(reflection, *, sanitize: Callable[[str], str] | None = None) -> list[str]:
    """Render a ``ReflectionContext`` as prompt lines, or ``[]`` when there is no
    reflective signal yet (first iteration, or no reflection supplied). Read entirely
    via ``getattr`` so an older brief without ``reflection`` is harmless (KTD1)."""
    if reflection is None:
        return []
    outcome = getattr(reflection, "outcome", "first")
    if outcome == "first":
        return []
    s = sanitize or (lambda x: str(x))
    lines: list[str] = []
    grade = s(getattr(reflection, "prior_grade", "") or "?")
    score = float(getattr(reflection, "prior_score", 0.0) or 0.0)
    lines.append(f"Your previous attempt left the tool at grade {grade} (score {score:g}).")
    if outcome in ("rolled_back", "reversed"):
        verb = (
            "rolled back (it did not improve the grade)"
            if outcome == "rolled_back"
            else "reversed by a decision review"
        )
        lines.append(
            f"That change was {verb}. Do NOT refine that same edit -- try a materially "
            f"different approach."
        )
    elif outcome == "accepted":
        lines.append("That change was kept; build on it without regressing it.")
    persistent = [s(fx) for fx in (getattr(reflection, "persistent_fixtures", []) or [])][:_MAX_PERSISTENT]
    if persistent:
        lines.append(
            f"These fixtures have resisted prior edits -- address them differently: "
            f"{', '.join(persistent)}."
        )
    feedback = getattr(reflection, "judge_feedback", "") or ""
    if feedback:
        lines.append(f"Referee feedback from the last grade: {s(feedback)}.")
    return lines
