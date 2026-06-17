"""U2/U3: Oracle protocol + resolver cascade tests (plan 2026-06-17)."""

from __future__ import annotations

from loopeng.adapters.base import Oracle, OracleVerdict
from loopeng.adapters.oracle import NoGroundingOracle
from loopeng.loop.fork_card import UNRESOLVED, ForkCard, ForkOption


def _card(chosen_default="a", **over):
    base = dict(
        id="fork-1",
        options=[ForkOption("a", "A"), ForkOption("b", "B")],
        spec_clause="spec silent here",
        chosen_default=chosen_default,
    )
    base.update(over)
    return ForkCard(**base)


# ----- U2: Oracle protocol + NoGroundingOracle ---------------------------


def test_no_grounding_oracle_returns_ungrounded_verdict():
    verdict = NoGroundingOracle().resolve(_card())
    assert verdict.chosen_option_id is None
    assert verdict.citations == []
    assert verdict.grounded is False


def test_no_grounding_oracle_satisfies_protocol():
    assert isinstance(NoGroundingOracle(), Oracle)


def test_oracle_verdict_grounded_requires_option_and_citation():
    assert OracleVerdict("a", ["cite"]).grounded is True
    assert OracleVerdict("a", []).grounded is False
    assert OracleVerdict(None, ["cite"]).grounded is False
