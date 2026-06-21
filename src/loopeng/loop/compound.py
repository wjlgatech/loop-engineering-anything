"""Compounding hook (U6, R7).

A thin wrapper that records a learning + regression test after an accepted fix.
The real binding drives /ce-compound; ``RecordingCompounder`` is an in-process
implementation used by the controller's tests and as a safe default until the
/ce-compound headless-invocation question is resolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecordingCompounder:
    """Captures compounded learnings in memory (test/default Compounder)."""

    entries: list = field(default_factory=list)

    def compound(
        self, summary: str, *, regression_test_ref: str | None = None, grade_delta: float | None = None
    ) -> None:
        self.entries.append(
            {"summary": summary, "regression_test_ref": regression_test_ref, "grade_delta": grade_delta}
        )
