"""Fork-Card resolver: decide one undetermined build decision (plan 2026-06-17 U3).

The cascade, in order:
  1. **spec determination** — if a spec hook can settle the choice, keep the
     default (no oracle call). v1 wires no spec source, so this is skipped; the
     living-spec patch (origin idea #6) fills it later.
  2. **oracle** — ask the persona/digital-twin. A *grounded* verdict (an option
     + citations) whose option differs from the agent's ``chosen_default`` is a
     ``reverse``; a grounded verdict that agrees is ``keep_default``.
  3. **escalate** — no grounding ⇒ the card is flagged ``unresolved`` for
     end-review. A build decision is never silently reversed on a guess.

``reverse`` fires only on a confident, grounded, *different* choice — so with the
v1 ``NoGroundingOracle`` the resolver never reverses, only escalates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .fork_card import UNRESOLVED, ForkCard

KEEP_DEFAULT = "keep_default"
REVERSE = "reverse"
ESCALATE = "escalate"


@dataclass(frozen=True)
class Resolution:
    """The resolver's decision on one Fork-Card."""

    decision: str  # keep_default | reverse | escalate
    chosen_option_id: str | None = None
    basis: Any = UNRESOLVED

    @property
    def is_reversal(self) -> bool:
        return self.decision == REVERSE

    @property
    def is_unresolved(self) -> bool:
        return self.decision == ESCALATE


class Resolver:
    """Maps a Fork-Card to a Resolution via spec → oracle → escalate.

    ``oracle`` implements ``adapters.base.Oracle``. ``spec`` is an optional
    callable ``(ForkCard) -> str | None`` returning the option id the spec
    determines, or ``None`` when the spec is silent (v1 default: ``None``).
    """

    def __init__(self, oracle, *, spec: Callable[[ForkCard], str | None] | None = None):
        self.oracle = oracle
        self.spec = spec

    def resolve(self, card: ForkCard) -> Resolution:
        # 1. spec determination — settle without the oracle when possible.
        if self.spec is not None:
            determined = self.spec(card)
            if determined is not None:
                return Resolution(KEEP_DEFAULT, determined, basis="spec")

        # 2. oracle — grounded answer can keep or reverse the default.
        verdict = self.oracle.resolve(card)
        if verdict.grounded:
            if card.chosen_default is not None and verdict.chosen_option_id == card.chosen_default:
                return Resolution(KEEP_DEFAULT, verdict.chosen_option_id, basis=list(verdict.citations))
            return Resolution(REVERSE, verdict.chosen_option_id, basis=list(verdict.citations))

        # 3. no grounding — flag for end-review (never reverse on a guess).
        return Resolution(ESCALATE, None, basis=UNRESOLVED)
