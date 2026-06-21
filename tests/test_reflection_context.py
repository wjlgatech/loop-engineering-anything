"""U1 (plan 2026-06-20): ReflectionContext model + additive RefactorBrief.reflection."""

from __future__ import annotations

from loopeng.adapters.base import ReflectionContext, RefactorBrief, Refiner


def test_reflection_context_all_fields_defaulted():
    rc = ReflectionContext()
    assert rc.outcome == "first"
    assert rc.prior_grade == "" and rc.prior_score == 0.0
    assert rc.prior_dims == {} and rc.persistent_fixtures == [] and rc.new_fixtures == []
    assert rc.attempted is None and rc.judge_feedback == ""


def test_reflection_context_mutable_defaults_are_independent():
    a, b = ReflectionContext(), ReflectionContext()
    assert a.prior_dims is not b.prior_dims  # field(default_factory), not a shared singleton
    assert a.persistent_fixtures is not b.persistent_fixtures


def test_refactor_brief_reflection_defaults_none():
    brief = RefactorBrief(goal="g", target_dimensions=[], failing_fixtures=[])
    assert brief.reflection is None


def test_refactor_brief_carries_populated_reflection():
    rc = ReflectionContext(prior_grade="C", outcome="rolled_back", persistent_fixtures=["fx1"])
    brief = RefactorBrief(goal="g", target_dimensions=["d"], failing_fixtures=["fx1"], reflection=rc)
    assert brief.reflection is rc
    assert brief.reflection.prior_grade == "C"
    assert brief.reflection.outcome == "rolled_back"


def test_existing_refiner_still_satisfies_protocol():
    # Adding reflection to RefactorBrief must not impose a new required attr on refiners.
    class OldRefiner:
        last_token_cost = None
        last_infra_failure = False
        last_fork_cards: list = []

        def refactor(self, tool_path, brief):
            return None

    assert isinstance(OldRefiner(), Refiner)
