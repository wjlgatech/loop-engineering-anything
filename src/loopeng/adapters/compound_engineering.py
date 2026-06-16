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

import json

from .base import RefactorBrief
from .safety import run_tool

DEFAULT_TIMEOUT = 30 * 60  # seconds
# `claude -p --output-format json` emits a result envelope carrying token usage.
# We request it so refine cost can be surfaced in the proof pack -- best-effort:
# if the envelope is absent/unparseable, token cost is simply omitted, never a
# fabricated value (R3). Threading the count into per-iteration store records is
# a controller-aware step deferred to the live-run unit (controller stays
# unchanged here -- KTD1); the parse mechanism lives here so it is ready + tested.
_USAGE_ARGS = ("--output-format", "json")


def parse_token_cost(stdout: str) -> int | None:
    """Extract total token usage from a ``claude -p --output-format json`` result
    envelope. Returns ``None`` if the output is not the expected JSON shape."""
    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return None
    total = 0
    found = False
    for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        val = usage.get(key)
        if isinstance(val, int):
            total += val
            found = True
    return total if found else None


class ClaudeCodeRefiner:
    """Drives ``/ce-work`` headlessly via ``claude -p`` (Refiner protocol)."""

    def __init__(self, *, executable: str = "claude", timeout: float = DEFAULT_TIMEOUT,
                 extra_args: tuple[str, ...] = ("--permission-mode", "acceptEdits", *_USAGE_ARGS)):
        self.executable = executable
        self.timeout = timeout
        self.extra_args = tuple(extra_args)
        self.last_token_cost: int | None = None

    def _build_prompt(self, brief: RefactorBrief) -> str:
        dims = ", ".join(brief.target_dimensions) or "the lowest-scoring dimensions"
        fixtures = ", ".join(brief.failing_fixtures) or "none reported"
        prompt = (
            f"/ce-work {brief.goal}\n"
            f"Prioritize these dimensions first: {dims}.\n"
            f"Failing fixtures to address: {fixtures}."
        )
        recurring = ", ".join(getattr(brief, "recurring_failures", []) or [])
        if recurring:
            prompt += (
                f"\nFixtures that recur across prior runs of this target "
                f"(watch for regressions, lower priority than the failing fixtures above): {recurring}."
            )
        return prompt

    def refactor(self, tool_path: str, brief: RefactorBrief) -> str | None:
        res = run_tool(
            [self.executable, "-p", self._build_prompt(brief), *self.extra_args],
            cwd=tool_path,
            timeout=self.timeout,
        )
        # Best-effort token accounting for the proof pack; None if unavailable.
        self.last_token_cost = parse_token_cost(res.stdout)
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
