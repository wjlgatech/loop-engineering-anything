"""U8 autonomous runner wiring tests (fakes; no real tools)."""

from __future__ import annotations

import pytest

from loopeng.adapters.base import GenerateResult, Verdict
from loopeng.autonomous.runner import run_loop, run_refine_loop
from loopeng.autonomous.report import render_report
from loopeng.config import Budget, Config
from loopeng.loop.checkpoint import NoopCheckpoint
from loopeng.loop.compound import RecordingCompounder
from loopeng.loop.controller import LoopState
from loopeng.memory.store import MemoryStore
from loopeng.preflight import ToolStatus


def v(grade, safety_ok=True):
    return Verdict(grade=grade, score=0.0, dims={"correctness": 30}, safety_ok=safety_ok)


class ScriptedJudge:
    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = 0

    def judge(self, tool_path):
        verdict = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return verdict


class FakeRefiner:
    def refactor(self, tool_path, brief):
        return "diff"


class FakeFactory:
    def __init__(self, ok=True, lane="service"):
        self.ok = ok
        self.lane = lane

    def generate(self, target, goal="", workdir="."):
        return GenerateResult(tool_path=workdir, lane=self.lane, ok=self.ok)


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "runner.db")
    yield s
    s.close()


def _run(store, tmp_path, judge, *, factory=None, config=None, budget=None, check_missing=None):
    return run_loop(
        "https://api.example.com",
        "improve it",
        judge=judge,
        refiner=FakeRefiner(),
        compounder=RecordingCompounder(),
        store=store,
        config=config or Config(),
        budget=budget or Budget(target_grade="A"),
        workspace_root=str(tmp_path / "ws"),
        factories={"printing-press": factory or FakeFactory()},
        checkpoint=NoopCheckpoint(),
        check_missing=check_missing or (lambda lane: []),
    )


def test_converges_end_to_end_and_report_renders(store, tmp_path):
    result = _run(store, tmp_path, ScriptedJudge([v("C"), v("B"), v("A")]))
    assert result.outcome.final_state is LoopState.CONVERGED
    report = render_report(store, result.run_id)
    assert "C -> B -> A" in report
    assert "converged" in report


def test_preflight_gate_blocks_before_work(store, tmp_path):
    blocked = [ToolStatus("cli-judge", "CLI-Judge", False, "not on PATH")]
    with pytest.raises(RuntimeError, match="preflight"):
        _run(store, tmp_path, ScriptedJudge([v("A")]), check_missing=lambda lane: blocked)


def test_credential_gate_blocks_when_env_missing(store, tmp_path, monkeypatch):
    monkeypatch.delenv("LOOP_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="credential"):
        _run(store, tmp_path, ScriptedJudge([v("A")]), config=Config(required_env=("LOOP_API_KEY",)))


def test_factory_failure_stops_run(store, tmp_path):
    result = _run(store, tmp_path, ScriptedJudge([v("A")]), factory=FakeFactory(ok=False))
    assert result.outcome.final_state is LoopState.STOPPED
    assert "generation failed" in result.outcome.reason


def test_blocked_safety_reported(store, tmp_path):
    result = _run(store, tmp_path, ScriptedJudge([v("C", safety_ok=False)]))
    assert result.outcome.final_state is LoopState.BLOCKED_SAFETY
    report = render_report(store, result.run_id)
    assert "blocked_safety" in report


# ----- U2: refine-only loop (proof pipeline) -----------------------------


def _refine(store, tool_path, judge, *, budget=None, check_missing=None, compounder=None, ws=None):
    return run_refine_loop(
        tool_path,
        "improve it",
        judge=judge,
        refiner=FakeRefiner(),
        compounder=compounder or RecordingCompounder(),
        store=store,
        workspace_root=ws or str(tool_path),
        budget=budget or Budget(target_grade="A"),
        checkpoint=NoopCheckpoint(),
        check_missing=check_missing or (lambda: []),
    )


def test_refine_only_records_before_baseline_and_after(store, tmp_path):
    tool = tmp_path / "ws" / "adopted"
    tool.mkdir(parents=True)
    result = _refine(store, str(tool), ScriptedJudge([v("C"), v("B"), v("A")]), ws=str(tmp_path / "ws"))
    assert result.outcome.final_state is LoopState.CONVERGED
    traj = store.grade_trajectory(result.run_id)
    assert traj[0] == "C"  # the adopted tool, judged as-is = baseline
    assert traj[-1] == "A"
    # wall-clock end stamped for the proof pack
    assert store.get_run(result.run_id).finished is not None


def test_refine_only_rejects_tool_outside_workspace(store, tmp_path):
    with pytest.raises(ValueError, match="outside the workspace"):
        _refine(store, "/etc", ScriptedJudge([v("A")]), ws=str(tmp_path / "ws"))


def test_refine_only_preflight_gate(store, tmp_path):
    tool = tmp_path / "ws" / "adopted"
    tool.mkdir(parents=True)
    blocked = [ToolStatus("cli-judge", "CLI-Judge", False, "not on PATH")]
    with pytest.raises(RuntimeError, match="preflight"):
        _refine(store, str(tool), ScriptedJudge([v("A")]), ws=str(tmp_path / "ws"),
                check_missing=lambda: blocked)


def test_refine_only_blocked_safety_at_baseline(store, tmp_path):
    tool = tmp_path / "ws" / "adopted"
    tool.mkdir(parents=True)
    result = _refine(store, str(tool), ScriptedJudge([v("C", safety_ok=False)]), ws=str(tmp_path / "ws"))
    assert result.outcome.final_state is LoopState.BLOCKED_SAFETY


def test_refine_only_already_grade_a_converges_at_baseline(store, tmp_path):
    tool = tmp_path / "ws" / "adopted"
    tool.mkdir(parents=True)
    result = _refine(store, str(tool), ScriptedJudge([v("A")]), ws=str(tmp_path / "ws"))
    assert result.outcome.final_state is LoopState.CONVERGED
    assert result.outcome.iterations == 1  # nothing to prove; converged as-is
