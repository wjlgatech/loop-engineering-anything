"""SpecRefiner — the `Refiner` for the spec stage (plan 2026-06-21 U8).

Rewrites a spec *document* against the grader's brief (lowest dims + named gaps +
reused spec-learnings), so it drops into the existing `LoopController` via the
`Refiner` protocol. The actual rewrite is delegated to an injectable ``editor`` so
the loop is testable without quota; the default editor shells to the planning
capability (`ce-plan`/`ce-brainstorm`) and is first-light-gated.
"""

from __future__ import annotations

import os

from .base import RefactorBrief

_SPEC_FILENAMES = ("spec.md", "SPEC.md")


def _resolve_spec_path(tool_path: str) -> str:
    if os.path.isdir(tool_path):
        for name in _SPEC_FILENAMES:
            p = os.path.join(tool_path, name)
            if os.path.isfile(p):
                return p
        return os.path.join(tool_path, "spec.md")
    return tool_path


class SpecRefiner:
    """Implements ``Refiner`` for specs. ``editor(spec_path, brief) -> bool`` applies
    edits and returns whether it changed the file; ``None`` (the default) means the
    live planning-capability editor, which is first-light-gated and reports an infra
    failure until wired (so the chain/controller treat it as retryable, not a crash)."""

    name = "spec-refiner"

    def __init__(self, editor=None):
        self.editor = editor
        self.last_token_cost: int | None = None
        self.last_infra_failure: bool = False
        self.last_fork_cards: list = []

    def refactor(self, tool_path: str, brief: RefactorBrief) -> str | None:
        self.last_infra_failure = False
        self.last_fork_cards = []
        if self.editor is None:
            # Live spec editor (ce-plan/ce-brainstorm) not wired yet -> infra failure
            # (first-light-gated); never a silent clean no-change.
            self.last_infra_failure = True
            return None
        spec_path = _resolve_spec_path(tool_path)
        changed = self.editor(spec_path, brief)
        return "spec-edited" if changed else None
