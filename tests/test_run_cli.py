"""U4: `loopeng run` wiring — generate -> resolve adapter -> run_refine_loop."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from loopeng.adapters.base import GenerateResult
from loopeng.adapters.llm_refiner import ChainedRefiner, FallbackLLMRefiner
from loopeng.autonomous.runner import RunResult
from loopeng.cli import main
from loopeng.loop.controller import LoopOutcome, LoopState
from loopeng.memory.store import MemoryStore


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Stub the heavy externals; capture what run_refine_loop is called with."""
    tool = tmp_path / "ws"
    tool.mkdir()
    adapter = tmp_path / "adapters" / "x.py"
    adapter.parent.mkdir()
    adapter.write_text("x\n")
    repo = tmp_path / "repo"
    repo.mkdir()  # an existing dir -> codebase lane -> cli-anything factory

    captured: dict = {}

    class FakeFactory:
        def generate(self, target, goal, workdir):
            return GenerateResult(tool_path=str(tool), lane="codebase", ok=True, manifest={})

    def fake_refine(tool_path, goal, **kw):
        captured["tool_path"] = tool_path
        captured["goal"] = goal
        captured.update(kw)
        return RunResult(
            run_id=7,
            outcome=LoopOutcome(LoopState.CONVERGED, "A", "ok", 2, score=0.0, dims={}),
            shippable=True,
        )

    monkeypatch.setattr("loopeng.cli.missing_for_lane", lambda lane: [])
    monkeypatch.setattr(
        "loopeng.autonomous.runner._default_factories",
        lambda: {"cli-anything": FakeFactory(), "printing-press": FakeFactory()},
    )
    monkeypatch.setattr("loopeng.autonomous.runner.run_refine_loop", fake_refine)
    monkeypatch.setattr(MemoryStore, "default", classmethod(lambda cls: MemoryStore(tmp_path / "db.sqlite")))
    return {"repo": repo, "adapter": adapter, "tool": tool, "captured": captured}


def test_run_drives_refine_loop_with_chain_and_protected_referee(wired):
    res = CliRunner().invoke(
        main,
        ["run", str(wired["repo"]), "--goal", "g", "--judge-adapter", str(wired["adapter"])],
    )
    assert res.exit_code == 0, res.output
    cap = wired["captured"]
    assert cap["tool_path"] == str(wired["tool"])
    assert isinstance(cap["refiner"], ChainedRefiner)  # default kind = chain
    # Referee protection actually wired (KTD3): adapter as referee, tool as maker tree.
    assert cap["referee_paths"] == [str(wired["adapter"])]
    assert cap["maker_write_paths"] == [str(wired["tool"])]
    assert "7" in res.output  # run id rendered
    assert "A" in res.output


def test_run_refiner_llm_uses_fallback_only(wired):
    res = CliRunner().invoke(
        main,
        ["run", str(wired["repo"]), "--goal", "g", "--judge-adapter", str(wired["adapter"]),
         "--refiner", "llm"],
    )
    assert res.exit_code == 0, res.output
    assert isinstance(wired["captured"]["refiner"], FallbackLLMRefiner)


def test_run_missing_tool_blocks_before_generate(wired, monkeypatch):
    class _Tool:
        label = "CLI-Judge (referee)"
    monkeypatch.setattr("loopeng.cli.missing_for_lane", lambda lane: [_Tool()])
    res = CliRunner().invoke(
        main, ["run", str(wired["repo"]), "--goal", "g", "--judge-adapter", str(wired["adapter"])]
    )
    assert res.exit_code != 0
    assert "CLI-Judge" in res.output
    assert "tool_path" not in wired["captured"]  # never generated


def test_run_adapter_discovery_failure_is_actionable(wired):
    # No --judge-adapter and the generated tool ships none -> fail closed.
    res = CliRunner().invoke(main, ["run", str(wired["repo"]), "--goal", "g"])
    assert res.exit_code != 0
    assert "judge-adapter" in res.output.lower()
    assert "tool_path" not in wired["captured"]  # loop never started


def test_run_scheduled_confirm_rejected(wired):
    res = CliRunner().invoke(
        main,
        ["run", str(wired["repo"]), "--goal", "g", "--judge-adapter", str(wired["adapter"]),
         "--scheduled", "--confirm"],
    )
    assert res.exit_code != 0
    assert "scheduled" in res.output.lower()
    assert "tool_path" not in wired["captured"]


def test_run_factory_failure_is_honest(wired, monkeypatch):
    class FailFactory:
        def generate(self, target, goal, workdir):
            return GenerateResult(tool_path=str(wired["tool"]), lane="codebase", ok=False,
                                  manifest={}, logs="boom")
    monkeypatch.setattr(
        "loopeng.autonomous.runner._default_factories",
        lambda: {"cli-anything": FailFactory(), "printing-press": FailFactory()},
    )
    res = CliRunner().invoke(
        main, ["run", str(wired["repo"]), "--goal", "g", "--judge-adapter", str(wired["adapter"])]
    )
    assert res.exit_code != 0
    assert "tool_path" not in wired["captured"]  # no loop on a failed generate
