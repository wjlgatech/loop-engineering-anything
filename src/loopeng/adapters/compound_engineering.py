"""Headless bindings for the refinement engine (U6 live binding; P0 #1).

Resolves the "can /ce-work and /ce-compound be driven unattended?" gate: yes —
via Claude Code's non-interactive print mode, ``claude -p "<prompt>"``. These
adapters implement the ``Refiner`` and ``Compounder`` protocols by invoking the
slash-commands as prompts in the tool's working directory.

What remains empirical (not a code gate): the *quality* of headless ``/ce-work``
output on a real target. The mechanism is settled here; a live run measures the
quality. Brief content is passed as a prompt argument, never interpolated into a
shell (``run_tool`` uses ``shell=False``).
"""

from __future__ import annotations

from .base import RefactorBrief
from .safety import run_tool

DEFAULT_TIMEOUT = 30 * 60  # seconds


class ClaudeCodeRefiner:
    """Drives ``/ce-work`` headlessly via ``claude -p`` (Refiner protocol)."""

    def __init__(self, *, executable: str = "claude", timeout: float = DEFAULT_TIMEOUT,
                 extra_args: tuple[str, ...] = ("--permission-mode", "acceptEdits")):
        self.executable = executable
        self.timeout = timeout
        self.extra_args = tuple(extra_args)

    def _build_prompt(self, brief: RefactorBrief) -> str:
        dims = ", ".join(brief.target_dimensions) or "the lowest-scoring dimensions"
        fixtures = ", ".join(brief.failing_fixtures) or "none reported"
        return (
            f"/ce-work {brief.goal}\n"
            f"Prioritize these dimensions first: {dims}.\n"
            f"Failing fixtures to address: {fixtures}."
        )

    def refactor(self, tool_path: str, brief: RefactorBrief) -> str | None:
        res = run_tool(
            [self.executable, "-p", self._build_prompt(brief), *self.extra_args],
            cwd=tool_path,
            timeout=self.timeout,
        )
        if not res.ok:
            return None
        # Reference the applied change by its diff summary; None when nothing changed.
        diff = run_tool(["git", "-C", tool_path, "diff", "--shortstat"], timeout=60)
        summary = diff.stdout.strip()
        return summary or None


class ClaudeCodeCompounder:
    """Drives ``/ce-compound`` headlessly via ``claude -p`` (Compounder protocol)."""

    def __init__(self, tool_path: str, *, executable: str = "claude", timeout: float = DEFAULT_TIMEOUT,
                 extra_args: tuple[str, ...] = ("--permission-mode", "acceptEdits")):
        self.tool_path = tool_path
        self.executable = executable
        self.timeout = timeout
        self.extra_args = tuple(extra_args)

    def compound(self, summary: str, *, regression_test_ref: str | None = None) -> None:
        prompt = (
            f"/ce-compound Document this learning and add a regression test so it "
            f"never recurs: {summary}"
        )
        if regression_test_ref:
            prompt += f"\nRelated change: {regression_test_ref}"
        run_tool([self.executable, "-p", prompt, *self.extra_args], cwd=self.tool_path, timeout=self.timeout)
