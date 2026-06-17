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

from ..loop.fork_card import ForkCard, ForkCardParseError
from .base import RefactorBrief
from .safety import is_infra_failure, run_tool

DEFAULT_TIMEOUT = 30 * 60  # seconds
# `claude -p --output-format json` emits a result envelope carrying token usage.
# We request it so refine cost can be surfaced in the proof pack -- best-effort:
# if the envelope is absent/unparseable, token cost is simply omitted, never a
# fabricated value (R3). Threading the count into per-iteration store records is
# a controller-aware step deferred to the live-run unit (controller stays
# unchanged here -- KTD1); the parse mechanism lives here so it is ready + tested.
_USAGE_ARGS = ("--output-format", "json")


def _safe_loads(stdout: str) -> dict | None:
    """Parse the ``claude -p --output-format json`` envelope once; ``None`` if it
    is not the expected JSON object. Token cost and fork cards are both read from
    this single parse in ``refactor`` (KTD1 -- no double ``json.loads``)."""
    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _token_cost_from(data: dict | None) -> int | None:
    """Total token usage from a parsed result envelope; ``None`` when absent."""
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


def _fork_cards_from(data: dict | None) -> list[ForkCard]:
    """Map a parsed envelope's ``fork_cards`` array to ``ForkCard`` objects.

    Defensive by contract: a malformed card is skipped (and its siblings kept),
    never raised -- a buggy emission must not crash the refiner (KTD1). An absent
    or non-list ``fork_cards`` yields an empty list.
    """
    raw = data.get("fork_cards") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    cards: list[ForkCard] = []
    for entry in raw:
        try:
            cards.append(ForkCard.from_dict(entry))
        except ForkCardParseError:
            continue
    return cards


def parse_token_cost(stdout: str) -> int | None:
    """Extract total token usage from a ``claude -p --output-format json`` result
    envelope. Returns ``None`` if the output is not the expected JSON shape."""
    return _token_cost_from(_safe_loads(stdout))


def parse_fork_cards(stdout: str) -> list[ForkCard]:
    """Extract emitted Fork-Cards from a ``claude -p --output-format json`` result
    envelope. Returns ``[]`` for non-JSON output or output with no ``fork_cards``
    key; skips malformed cards rather than raising."""
    return _fork_cards_from(_safe_loads(stdout))


class ClaudeCodeRefiner:
    """Drives ``/ce-work`` headlessly via ``claude -p`` (Refiner protocol)."""

    def __init__(self, *, executable: str = "claude", timeout: float = DEFAULT_TIMEOUT,
                 extra_args: tuple[str, ...] = ("--permission-mode", "acceptEdits", *_USAGE_ARGS)):
        self.executable = executable
        self.timeout = timeout
        self.extra_args = tuple(extra_args)
        self.last_token_cost: int | None = None
        # Set by ``refactor`` (U3): True when the last invocation failed for infra
        # reasons (timeout / non-zero exit / missing executable). The controller
        # reads this to retry transient failures without confusing them with a
        # clean no-change result or a quality regression.
        self.last_infra_failure: bool = False
        # Fork-Cards the agent emitted on the last refactor (plan 2026-06-17 U4):
        # build decisions the spec/northstar did not determine. Parsed off the same
        # JSON envelope as token cost; the controller reads it protocol-bound.
        self.last_fork_cards: list[ForkCard] = []

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
        upstream = getattr(brief, "upstream_outcomes", []) or []
        if upstream:
            lines = "; ".join(
                f"{u.get('item', '?')}: {u.get('final_state', '?')} (grade {u.get('grade', '?')})"
                for u in upstream
            )
            prompt += (
                f"\nUpstream fleet items this work depends on (context only): {lines}."
            )
        # Fork-Card emission convention (plan 2026-06-17 U4): the supervised loop
        # needs undetermined decisions to be visible, not silently defaulted. Do
        # NOT stop to ask -- emit the decision as data and keep building.
        prompt += (
            "\n\nDecision protocol: when a choice is NOT determined by the goal/spec above "
            "(the spec is silent, vague, or contradictory), do NOT pause to ask. Instead pick "
            "the most reversible reasonable default, keep building on it, and record the fork in "
            "your final JSON result under a top-level \"fork_cards\" array. Each entry: "
            "{id, options:[{id,label,description}], spec_clause, chosen_default (an option id), "
            "reversibility (reversible|hard_to_reverse|irreversible), blast_radius "
            "(local|module|cross_cutting)}. Decisions the goal/spec DO determine need no card."
        )
        return prompt

    def refactor(self, tool_path: str, brief: RefactorBrief) -> str | None:
        res = run_tool(
            [self.executable, "-p", self._build_prompt(brief), *self.extra_args],
            cwd=tool_path,
            timeout=self.timeout,
        )
        # Parse the JSON envelope once for both token cost and fork cards (KTD1).
        envelope = _safe_loads(res.stdout)
        self.last_token_cost = _token_cost_from(envelope)
        self.last_fork_cards = _fork_cards_from(envelope)
        self.last_infra_failure = is_infra_failure(res)
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
