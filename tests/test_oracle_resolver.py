"""U2/U3: Oracle protocol + resolver cascade tests (plan 2026-06-17)."""

from __future__ import annotations

from loopeng.adapters.base import Oracle, OracleVerdict
from loopeng.adapters.oracle import NoGroundingOracle
from loopeng.loop.fork_card import UNRESOLVED, ForkCard, ForkOption
from loopeng.loop.resolver import ESCALATE, KEEP_DEFAULT, REVERSE, Resolver


class FakeOracle:
    """Returns a scripted verdict, recording how many times it was asked."""

    def __init__(self, verdict):
        self.verdict = verdict
        self.calls = 0

    def resolve(self, fork_card):
        self.calls += 1
        return self.verdict


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


# ----- U3: resolver cascade ----------------------------------------------


def test_spec_determines_keeps_default_without_calling_oracle():
    oracle = FakeOracle(OracleVerdict("b", ["cite"]))  # would reverse if reached
    resolver = Resolver(oracle, spec=lambda card: "a")
    res = resolver.resolve(_card(chosen_default="a"))
    assert res.decision == KEEP_DEFAULT
    assert res.chosen_option_id == "a"
    assert oracle.calls == 0  # spec settled it; oracle never consulted


def test_oracle_grounded_different_option_reverses():
    oracle = FakeOracle(OracleVerdict("b", ["kernel.yaml:3"]))
    res = Resolver(oracle).resolve(_card(chosen_default="a"))
    assert res.decision == REVERSE
    assert res.chosen_option_id == "b"
    assert res.basis == ["kernel.yaml:3"]
    assert res.is_reversal


def test_oracle_grounded_same_option_keeps_default():
    oracle = FakeOracle(OracleVerdict("a", ["kernel.yaml:3"]))
    res = Resolver(oracle).resolve(_card(chosen_default="a"))
    assert res.decision == KEEP_DEFAULT
    assert res.chosen_option_id == "a"


def test_oracle_no_grounding_escalates():
    res = Resolver(NoGroundingOracle()).resolve(_card(chosen_default="a"))
    assert res.decision == ESCALATE
    assert res.basis == UNRESOLVED
    assert res.is_unresolved


def test_no_grounding_never_reverses_even_with_an_option():
    # An option id but no citations is NOT grounded -> escalate, never reverse.
    oracle = FakeOracle(OracleVerdict("b", []))
    res = Resolver(oracle).resolve(_card(chosen_default="a"))
    assert res.decision == ESCALATE
    assert not res.is_reversal


def test_grounded_with_no_chosen_default_keeps_not_reverses():
    # No committed default -> nothing to reverse; adopt the grounded option.
    oracle = FakeOracle(OracleVerdict("b", ["kernel.yaml:9"]))
    res = Resolver(oracle).resolve(_card(chosen_default=None))
    assert res.decision == KEEP_DEFAULT
    assert res.chosen_option_id == "b"
    assert res.basis == ["kernel.yaml:9"]
    assert not res.is_reversal
