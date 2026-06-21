"""SpecJudge — the `Judge` for specs (plan 2026-06-21 U7).

Grades a spec *document* with the deterministic rubric and returns a `Verdict`, so it
drops into the existing `LoopController` via the `Judge` protocol unchanged. It reads
ONLY the spec artifact at ``tool_path`` — never a `RefactorBrief` / `reused_learnings`
— so maker≠checker holds by construction for the spec stage (R9).
"""

from __future__ import annotations

import os

from ..spec.rubric import score_spec
from .base import Verdict

_SPEC_FILENAMES = ("spec.md", "SPEC.md")


def _read_spec(tool_path: str) -> str:
    """Read the spec text at ``tool_path`` (a file, or a dir containing spec.md).
    Fail-closed: anything unreadable returns "" so the rubric grades it F."""
    try:
        if os.path.isdir(tool_path):
            for name in _SPEC_FILENAMES:
                p = os.path.join(tool_path, name)
                if os.path.isfile(p):
                    return _read_file(p)
            return ""
        return _read_file(tool_path)
    except OSError:
        return ""


def _read_file(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class SpecJudge:
    """Implements the ``Judge`` protocol by scoring a spec document with the rubric.

    Deterministic (same spec -> same Verdict), maker-distinct from the spec generator
    and refiner, and fail-closed on a missing/unreadable spec.
    """

    def __init__(self, *, suite: str = "spec"):
        self.suite = suite

    def judge(self, tool_path: str) -> Verdict:
        data = score_spec(_read_spec(tool_path))
        return Verdict(
            grade=data["grade"],
            score=data["score"],
            dims=data["dims"],
            safety_ok=True,  # specs carry no safety gate; quality is the rubric score
            failing_fixtures=list(data["failing_fixtures"]),
            feedback=data["feedback"],
        )
