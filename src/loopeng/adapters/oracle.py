"""Oracle bindings: the persona/digital-twin behind the Fork-Card resolver (plan 2026-06-17 U2).

v1 ships only ``NoGroundingOracle`` -- a deliberate no-op that never grounds, so
every spec-silent fork keeps its reversible default and is flagged for end-review.
This makes the headless channel end-to-end (emit -> parse -> resolve -> record ->
surface) with honest v1 behavior: nothing is auto-reversed until a real twin-backed
oracle (origin idea #2) replaces this seam.
"""

from __future__ import annotations

from .base import OracleVerdict


class NoGroundingOracle:
    """The v1 default oracle: returns an ungrounded verdict for every card.

    A real oracle would score the card's options against the Vision Kernel +
    person-map and return a grounded ``OracleVerdict`` with citations. Until then,
    the resolver always escalates (no grounding), which is the correct, honest
    behavior -- a build decision is never silently reversed on a guess.
    """

    def resolve(self, fork_card) -> OracleVerdict:  # noqa: ARG002 -- v1 ignores the card
        return OracleVerdict(chosen_option_id=None, citations=[])
