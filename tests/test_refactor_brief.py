"""U1 refactor-brief tests: cross-run recurring-failure injection.

Live signal (the current verdict's failing fixtures) is never demoted below
stale cross-run history; only fixtures that recur AND fail now are re-prioritized,
and recurring-but-passing fixtures ride along as advisory context only.
"""

from __future__ import annotations

from loopeng.adapters.base import Verdict
from loopeng.loop.refactor_brief import build_refactor_brief


def _verdict(dims=None, failing=None, grade="C"):
    return Verdict(
        grade=grade,
        score=0.0,
        dims=dims or {"correctness": 30, "safety": 20},
        safety_ok=True,
        failing_fixtures=failing or [],
    )


def test_no_recurring_history_is_identical_to_baseline():
    v = _verdict(failing=["live_a", "live_b"])
    base = build_refactor_brief(v, "goal")
    with_empty = build_refactor_brief(v, "goal", recurring_failures=[])
    assert base.failing_fixtures == ["live_a", "live_b"]
    assert base.recurring_failures == []
    assert with_empty.failing_fixtures == base.failing_fixtures
    assert with_empty.recurring_failures == []


def test_recurring_and_live_fixture_is_reprioritized_to_front():
    # live order has the recurring fixture last; it should jump to the front.
    v = _verdict(failing=["live_only", "recurs_and_fails"])
    brief = build_refactor_brief(v, "goal", recurring_failures=["recurs_and_fails"])
    assert brief.failing_fixtures == ["recurs_and_fails", "live_only"]
    # it's a live failure, so it stays in failing_fixtures, not advisory.
    assert "recurs_and_fails" not in brief.recurring_failures


def test_recurring_but_passing_fixture_is_advisory_not_promoted():
    # a historically-recurring fixture that is NOT failing now must not be
    # promoted ahead of a currently-failing one -- it goes to advisory context.
    v = _verdict(failing=["currently_failing"])
    brief = build_refactor_brief(v, "goal", recurring_failures=["passing_now"])
    assert brief.failing_fixtures == ["currently_failing"]
    assert brief.recurring_failures == ["passing_now"]


def test_live_failures_never_demoted_below_history():
    v = _verdict(failing=["live_a", "live_b"])
    # only history, none currently failing -> live order preserved, history advisory.
    brief = build_refactor_brief(v, "goal", recurring_failures=["old_1", "old_2"])
    assert brief.failing_fixtures == ["live_a", "live_b"]
    assert brief.recurring_failures == ["old_1", "old_2"]


def test_exclude_dims_demotes_to_back_for_rotation():
    # ranked lowest-first would be a, b, c; excluding "a" rotates the lead to b.
    v = _verdict(dims={"a": 10, "b": 20, "c": 30})
    brief = build_refactor_brief(v, "goal", exclude_dims=["a"])
    assert brief.target_dimensions == ["b", "c", "a"]


def test_exclude_dims_none_keeps_lowest_first_ranking():
    v = _verdict(dims={"a": 10, "b": 20, "c": 30})
    brief = build_refactor_brief(v, "goal")
    assert brief.target_dimensions == ["a", "b", "c"]


def test_upstream_outcomes_carried_on_brief():
    # plan-006 U3: caller-injected upstream fleet outcomes ride on the brief.
    v = _verdict(failing=["x"])
    brief = build_refactor_brief(v, "g", upstream_outcomes=[{"item": "A", "grade": "A"}])
    assert brief.upstream_outcomes == [{"item": "A", "grade": "A"}]


def test_no_upstream_outcomes_defaults_empty():
    v = _verdict(failing=["x"])
    brief = build_refactor_brief(v, "g")
    assert brief.upstream_outcomes == []
