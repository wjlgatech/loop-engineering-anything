"""U6 loop-controller integration tests against recorded verdicts.

This is the cheap loop-dynamics validation the doc-review asked for: drive the
controller with scripted CLI-Judge verdicts (no live generation) and assert it
converges, blocks on safety, plateaus, hits budget, and rolls back regressions
correctly -- the safety and rollback paths built test-first per U6.
"""

from __future__ import annotations

import pytest

from loopeng.adapters.base import Verdict
from loopeng.config import Budget
from loopeng.loop.compound import RecordingCompounder
from loopeng.loop.controller import LoopController, LoopState
from loopeng.memory.store import MemoryStore


def v(grade, safety_ok=True, dims=None, fixtures=None):
    return Verdict(
        grade=grade,
        score=0.0,
        dims=dims or {"correctness": 30, "safety": 20},
        safety_ok=safety_ok,
        failing_fixtures=fixtures or [],
    )


class ScriptedJudge:
    """Returns recorded verdicts in sequence; repeats the last when exhausted."""

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = 0

    def judge(self, tool_path):
        verdict = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return verdict


class FakeRefiner:
    def __init__(self):
        self.calls = 0

    def refactor(self, tool_path, brief):
        self.calls += 1
        return f"diff-{self.calls}"


class FakeCheckpoint:
    def __init__(self):
        self.snapshots = 0
        self.restores = 0

    def snapshot(self):
        self.snapshots += 1
        return f"ckpt-{self.snapshots}"

    def restore(self, token):
        self.restores += 1


class CapturingRefiner:
    """Records every brief it is handed so tests can assert on brief content."""

    def __init__(self):
        self.briefs = []

    def refactor(self, tool_path, brief):
        self.briefs.append(brief)
        return f"diff-{len(self.briefs)}"


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "loop.db")
    yield s
    s.close()


def _controller(store, judge, budget=None):
    refiner = FakeRefiner()
    compounder = RecordingCompounder()
    checkpoint = FakeCheckpoint()
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=compounder,
        checkpoint=checkpoint,
        store=store,
        budget=budget or Budget(),
    )
    return ctrl, refiner, compounder, checkpoint


def test_converges_and_compounds(store):
    judge = ScriptedJudge([v("C"), v("B"), v("A")])
    ctrl, refiner, compounder, _ = _controller(store, judge, Budget(target_grade="A"))
    run_id = store.create_run("t", "service", "improve", "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.CONVERGED
    assert outcome.grade == "A"
    assert refiner.calls == 2  # C->B, B->A
    assert len(compounder.entries) == 2  # one compound per accepted improvement
    assert store.get_run(run_id).status == "converged"


def test_initial_safety_failure_blocks_without_refactor(store):
    judge = ScriptedJudge([v("C", safety_ok=False)])
    ctrl, refiner, compounder, _ = _controller(store, judge)
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.BLOCKED_SAFETY
    assert refiner.calls == 0  # never attempt to refine an unsafe tool
    assert compounder.entries == []
    assert store.get_run(run_id).status == "blocked_safety"


def test_safety_failure_mid_loop_rolls_back_and_blocks(store):
    judge = ScriptedJudge([v("C"), v("B", safety_ok=False)])
    ctrl, refiner, compounder, checkpoint = _controller(store, judge)
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.BLOCKED_SAFETY
    assert checkpoint.restores == 1  # the unsafe change is rolled back
    assert compounder.entries == []  # never compound an unsafe iteration


def test_plateau_stops(store):
    judge = ScriptedJudge([v("C"), v("C"), v("C")])
    ctrl, refiner, compounder, checkpoint = _controller(
        store, judge, Budget(plateau_patience=2, max_iterations=99)
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.STOPPED
    assert "plateau" in outcome.reason
    assert compounder.entries == []  # no gains -> nothing compounded
    assert checkpoint.restores >= 1  # no-gain iterations rolled back


def test_max_iterations_stops(store):
    judge = ScriptedJudge([v("C"), v("C"), v("C")])
    ctrl, *_ = _controller(store, judge, Budget(plateau_patience=99, max_iterations=3))
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.STOPPED
    assert "max iterations" in outcome.reason


class RecordingCompressor:
    def __init__(self, after_verdict):
        self.after = after_verdict
        self.runs = 0

    def run(self, run_id, tool_path):
        from loopeng.compression import CompressionResult

        self.runs += 1
        return CompressionResult(True, self.after, self.after, "stub")


def test_compressor_fires_on_cadence(store):
    # Improvements C->B->A->A... ; compression every 1 accepted fix.
    judge = ScriptedJudge([v("C"), v("B"), v("A")])
    refiner = FakeRefiner()
    compounder = RecordingCompounder()
    checkpoint = FakeCheckpoint()
    compressor = RecordingCompressor(after_verdict=v("B"))
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=compounder,
        checkpoint=checkpoint,
        store=store,
        budget=Budget(target_grade="A", compression_interval=1),
        compressor=compressor,
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    ctrl.run(run_id, "tool/")
    # At least one accepted fix -> compressor ran at least once.
    assert compressor.runs >= 1


def test_no_compressor_means_no_compression(store):
    judge = ScriptedJudge([v("C"), v("A")])
    ctrl, *_ = _controller(store, judge, Budget(target_grade="A"))
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    outcome = ctrl.run(run_id, "tool/")
    assert outcome.final_state is LoopState.CONVERGED  # unchanged behavior


def test_regression_rolls_back_and_does_not_compound_transient(store):
    # B then a worse C (regression -> rollback, no compound), then A (accepted).
    judge = ScriptedJudge([v("B"), v("C"), v("A")])
    ctrl, refiner, compounder, checkpoint = _controller(store, judge, Budget(target_grade="A"))
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.CONVERGED
    assert checkpoint.restores == 1  # the C regression was rolled back
    # Only the B->A improvement compounds; the transient C never does.
    assert len(compounder.entries) == 1
    assert "-> A" in compounder.entries[0]["summary"]


def test_recurring_failures_injected_into_brief(store):
    # Two prior runs of target "t" both fail "pagination_drift".
    for _ in range(2):
        pr = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
        store.record_iteration(pr, 1, "C", {}, safety_ok=True, failing_fixtures=["pagination_drift"])
    # Current run: verdict fails a live-only fixture plus the recurring one.
    judge = ScriptedJudge([v("C", fixtures=["live_only", "pagination_drift"]), v("A")])
    refiner = CapturingRefiner()
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_grade="A"),
    )
    run_id = store.create_run("t", "service", "improve", "2026-06-15T00:00:00Z")

    ctrl.run(run_id, "tool/")

    assert refiner.briefs, "refiner should have been called at least once"
    brief = refiner.briefs[0]
    # recurring AND currently-failing -> promoted to the front; live-only stays.
    assert brief.failing_fixtures[0] == "pagination_drift"
    assert "live_only" in brief.failing_fixtures


import logging  # noqa: E402


class CostReportingRefiner:
    """A refiner that reports a fixed per-refactor token cost (U4)."""

    def __init__(self, cost):
        self.last_token_cost = cost
        self.calls = 0

    def refactor(self, tool_path, brief):
        self.calls += 1
        return f"diff-{self.calls}"


def test_token_budget_enforced_with_cost_reporting_refiner(store):
    # Never converges; each refactor reports 600 tokens; budget 1000 -> stops on cost.
    judge = ScriptedJudge([v("C")])
    refiner = CostReportingRefiner(cost=600)
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_grade="A", token_budget=1000, max_iterations=99, plateau_patience=99),
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    # Regression guard: tokens_spent now reflects reported cost, so the gate fires
    # (previously it compared against a constant 0 and never tripped).
    assert outcome.final_state is LoopState.STOPPED
    assert "token" in outcome.reason


def test_token_budget_warns_when_refiner_reports_no_cost(store, caplog):
    judge = ScriptedJudge([v("C")])
    refiner = FakeRefiner()  # no last_token_cost attribute
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_grade="A", token_budget=1000, max_iterations=2, plateau_patience=99),
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    with caplog.at_level(logging.WARNING):
        outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.STOPPED  # falls through to max_iterations
    assert any("token gate cannot fire" in r.getMessage() for r in caplog.records)


def test_wall_clock_budget_terminates_run(store):
    judge = ScriptedJudge([v("C")])
    ctrl = LoopController(
        judge=judge,
        refiner=FakeRefiner(),
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_grade="A", max_wall_seconds=0.0, max_iterations=99, plateau_patience=99),
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.STOPPED
    assert "wall-clock" in outcome.reason


class FlakyRefiner:
    """Fails infra-style for the first ``fail_times`` calls, then succeeds (U3)."""

    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0
        self.last_infra_failure = False
        self.last_token_cost = None

    def refactor(self, tool_path, brief):
        self.calls += 1
        if self.calls <= self.fail_times:
            self.last_infra_failure = True
            return None
        self.last_infra_failure = False
        return f"diff-{self.calls}"


def _noop_sleep(_seconds):
    return None


def test_infra_failure_is_retried_and_recovers(store):
    # One transient failure then success within one logical iteration.
    judge = ScriptedJudge([v("C"), v("A")])
    refiner = FlakyRefiner(fail_times=1)
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_grade="A", max_tool_retries=2),
        sleeper=_noop_sleep,
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.CONVERGED
    assert refiner.calls == 2  # 1 infra fail + 1 success, single iteration
    # Only one logical iteration past the initial judge -> n == 2.
    assert outcome.iterations == 2


def test_infra_retries_are_bounded(store):
    # Always fails infra-style; retries are capped so total calls are bounded.
    judge = ScriptedJudge([v("C")])
    refiner = FlakyRefiner(fail_times=99)
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_grade="A", max_tool_retries=2, max_iterations=2, plateau_patience=99),
        sleeper=_noop_sleep,
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.STOPPED
    # One iteration's refactor = 1 initial call + max_tool_retries (2) = 3 calls.
    assert refiner.calls == 3


def test_safety_failure_is_never_retried(store):
    # Refiner always succeeds; the judge returns an unsafe verdict post-refactor.
    judge = ScriptedJudge([v("C"), v("C", safety_ok=False)])
    refiner = FlakyRefiner(fail_times=0)
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_grade="A", max_tool_retries=2),
        sleeper=_noop_sleep,
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.BLOCKED_SAFETY
    assert refiner.calls == 1  # the safety failure (post-judge) triggered no retry


def test_plateau_pivots_zero_stops_immediately(store):
    # Characterization of the original behavior: plateau -> STOPPED, no pivot.
    judge = ScriptedJudge([v("C")])
    ctrl, refiner, compounder, _ = _controller(
        store, judge, Budget(plateau_patience=2, max_iterations=99, plateau_pivots=0)
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.STOPPED
    assert "plateau" in outcome.reason
    assert refiner.calls == 2  # plateau detected at iteration 3, no pivot


def test_plateau_triggers_one_pivot_then_stops(store):
    judge = ScriptedJudge([v("C")])
    refiner = CapturingRefiner()
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(plateau_patience=2, max_iterations=99, plateau_pivots=1),
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.STOPPED
    assert "plateau" in outcome.reason
    # The pivot rotates the lead dimension: pre-pivot briefs lead with the lowest
    # dim ("safety"=20), post-pivot briefs rotate to the next-lowest ("correctness").
    leads = [b.target_dimensions[0] for b in refiner.briefs]
    assert "safety" in leads and "correctness" in leads


def test_cap_wins_over_plateau_no_pivot(store):
    judge = ScriptedJudge([v("C")])
    refiner = CapturingRefiner()
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(plateau_patience=2, max_iterations=3, plateau_pivots=1),
    )
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.STOPPED
    assert "max iterations" in outcome.reason  # cap reason, not plateau
    # No pivot fired -> never rotated off the lowest dimension.
    leads = [b.target_dimensions[0] for b in refiner.briefs]
    assert all(lead == "safety" for lead in leads)


def test_upstream_context_threads_into_brief(store):
    # plan-006 U3: a LoopController given upstream_context surfaces it on the brief;
    # absent, the brief carries none (backward compatible).
    judge = ScriptedJudge([v("C"), v("A")])
    refiner = CapturingRefiner()
    ctrl = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_grade="A"),
        upstream_context=[{"item": "A", "grade": "A", "final_state": "converged"}],
    )
    run_id = store.create_run("t", "service", "improve", "2026-06-15T00:00:00Z")
    ctrl.run(run_id, "tool/")
    assert refiner.briefs[0].upstream_outcomes == [
        {"item": "A", "grade": "A", "final_state": "converged"}
    ]


def test_no_upstream_context_brief_has_empty_upstream(store):
    judge = ScriptedJudge([v("C"), v("A")])
    refiner = CapturingRefiner()
    ctrl = LoopController(
        judge=judge, refiner=refiner, compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(), store=store, budget=Budget(target_grade="A"),
    )
    run_id = store.create_run("t", "service", "improve", "2026-06-15T00:00:00Z")
    ctrl.run(run_id, "tool/")
    assert refiner.briefs[0].upstream_outcomes == []
