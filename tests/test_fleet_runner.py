"""U5: default_fleet_runner drives a real refine loop per item in its worktree."""

from __future__ import annotations

import pytest

from loopeng.adapters.base import GenerateResult
from loopeng.adapters.llm_refiner import ChainedRefiner
from loopeng.autonomous.runner import RunResult
from loopeng.loop.controller import LoopOutcome, LoopState
from loopeng.memory.fleet_state import FleetItem, FleetItemStatus
from loopeng.memory.store import MemoryStore
from loopeng.orchestration.coordinator import default_fleet_runner


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "f.db")
    yield s
    s.close()


def test_runner_drives_refine_loop_per_item(store, tmp_path, monkeypatch):
    tool = tmp_path / "wt"
    tool.mkdir()
    captured: dict = {}

    class FakeFactory:
        def generate(self, target, goal, workdir):
            captured["gen_workdir"] = workdir
            return GenerateResult(tool_path=str(tool), lane="service", ok=True, manifest={})

    def fake_refine(tool_path, goal, **kw):
        captured["tool_path"] = tool_path
        captured["goal"] = goal
        captured.update(kw)
        return RunResult(
            run_id=5,
            outcome=LoopOutcome(LoopState.CONVERGED, "A", "ok", 1, score=0.0, dims={}),
            shippable=True,
        )

    monkeypatch.setattr(
        "loopeng.autonomous.runner._default_factories",
        lambda: {"printing-press": FakeFactory(), "cli-anything": FakeFactory()},
    )
    monkeypatch.setattr("loopeng.autonomous.runner.run_refine_loop", fake_refine)

    runner = default_fleet_runner(
        store=store, fleet_goal="fleet goal", judge_adapter_override=str(tmp_path / "adapter.py"),
        refiner_kind="chain",
    )
    # make the override exist + out-of-jail
    (tmp_path / "adapter.py").write_text("x\n")

    item = FleetItem(
        id=1, fleet_id=1, key="a", status=FleetItemStatus.RUNNING,
        target="https://api.example.com", goal="item goal",
    )
    res = runner(item, str(tool / "worktree"), [{"item": "dep", "grade": "A"}])

    assert res.run_id == 5
    assert captured["tool_path"] == str(tool)
    assert captured["goal"] == "item goal"  # per-item goal preferred over fleet goal
    assert isinstance(captured["refiner"], ChainedRefiner)
    assert captured["referee_paths"] == [str(tmp_path / "adapter.py")]
    assert captured["maker_write_paths"] == [str(tool)]
    assert captured["upstream_context"] == [{"item": "dep", "grade": "A"}]
    assert captured["gen_workdir"] == str(tool / "worktree")  # generated into the item worktree


def test_runner_item_goal_falls_back_to_fleet_goal(store, tmp_path, monkeypatch):
    tool = tmp_path / "wt"; tool.mkdir()
    (tmp_path / "adapter.py").write_text("x\n")
    captured: dict = {}

    class FakeFactory:
        def generate(self, target, goal, workdir):
            return GenerateResult(tool_path=str(tool), lane="service", ok=True, manifest={})

    def fake_refine(tool_path, goal, **kw):
        captured["goal"] = goal
        return RunResult(run_id=1, outcome=LoopOutcome(LoopState.CONVERGED, "A", "", 1, score=0.0, dims={}), shippable=True)

    monkeypatch.setattr("loopeng.autonomous.runner._default_factories",
                        lambda: {"printing-press": FakeFactory()})
    monkeypatch.setattr("loopeng.autonomous.runner.run_refine_loop", fake_refine)

    runner = default_fleet_runner(store=store, fleet_goal="the fleet goal",
                                  judge_adapter_override=str(tmp_path / "adapter.py"))
    item = FleetItem(id=1, fleet_id=1, key="a", status=FleetItemStatus.RUNNING,
                     target="https://x", goal=None)  # no item goal
    runner(item, str(tool / "w"), [])
    assert captured["goal"] == "the fleet goal"


def test_runner_failed_generate_returns_stopped(store, tmp_path, monkeypatch):
    tool = tmp_path / "wt"; tool.mkdir()

    class FailFactory:
        def generate(self, target, goal, workdir):
            return GenerateResult(tool_path=str(tool), lane="service", ok=False, manifest={}, logs="boom")

    monkeypatch.setattr("loopeng.autonomous.runner._default_factories",
                        lambda: {"printing-press": FailFactory()})
    runner = default_fleet_runner(store=store, fleet_goal="g",
                                  judge_adapter_override=str(tmp_path / "adapter.py"))
    item = FleetItem(id=1, fleet_id=1, key="a", status=FleetItemStatus.RUNNING, target="https://x")
    res = runner(item, str(tool / "w"), [])
    assert res.outcome.final_state is LoopState.STOPPED
    assert res.shippable is False
