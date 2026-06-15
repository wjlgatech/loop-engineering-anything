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
