"""SpecRefiner — the `Refiner` for the spec stage (plan 2026-06-21 U8).

Rewrites a spec *document* against the grader's brief (lowest dims + named gaps +
reused spec-learnings), so it drops into the existing `LoopController` via the
`Refiner` protocol. The actual rewrite is delegated to an injectable ``editor`` so
the loop is testable without quota; the default editor shells to the planning
capability (`ce-plan`/`ce-brainstorm`) and is first-light-gated.
"""

from __future__ import annotations

import hashlib
import os

from .base import RefactorBrief
from .safety import is_infra_failure, run_tool

_SPEC_FILENAMES = ("spec.md", "SPEC.md")
_DEFAULT_TIMEOUT = 30 * 60


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

    def __init__(self, editor=None, *, live: bool = False, executable: str = "claude",
                 timeout: float = _DEFAULT_TIMEOUT):
        self.editor = editor
        self.live = live
        self.executable = executable
        self.timeout = timeout
        self.last_token_cost: int | None = None
        self.last_infra_failure: bool = False
        self.last_fork_cards: list = []

    def refactor(self, tool_path: str, brief: RefactorBrief) -> str | None:
        self.last_infra_failure = False
        self.last_fork_cards = []
        spec_path = _resolve_spec_path(tool_path)
        if self.editor is not None:
            changed = self.editor(spec_path, brief)
            return "spec-edited" if changed else None
        if self.live:
            return self._claude_edit(spec_path, brief)
        # Neither an injected editor nor live wiring -> not runnable; report an infra
        # failure (first-light-gated), never a silent clean no-change.
        self.last_infra_failure = True
        return None

    def _claude_edit(self, spec_path: str, brief: RefactorBrief) -> str | None:
        """Live editor: shell to the planning capability to rewrite the spec file in
        place, addressing the grader's brief. Returns a diff_ref iff the file changed;
        sets ``last_infra_failure`` on a non-zero/timeout exit so the controller retries
        a transient failure rather than treating it as a clean no-change."""
        before = _digest(spec_path)
        dims = ", ".join(brief.target_dimensions) or "the weakest dimensions"
        gaps = ", ".join(brief.failing_fixtures) or "none reported"
        reused = "; ".join(getattr(brief, "reused_learnings", []) or [])
        prompt = (
            f"/ce-plan Improve the spec at {os.path.basename(spec_path)} in place. "
            f"Raise these dimensions first: {dims}. Address these gaps: {gaps}."
        )
        if reused:
            prompt += f" Lessons from prior specs (reuse what worked): {reused}."
        res = run_tool([self.executable, "-p", prompt], cwd=os.path.dirname(spec_path) or ".",
                       timeout=self.timeout)
        if res is not None and is_infra_failure(res):
            self.last_infra_failure = True
            return None
        return "spec-edited" if _digest(spec_path) != before else None


def _digest(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None
