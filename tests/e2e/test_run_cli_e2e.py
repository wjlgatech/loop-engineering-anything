"""U6 end-to-end: the public CLI drives a real loop with the leaf tools faked.

Unlike the gated reference/proof e2e tests, this runs everywhere: it fakes the
three external tools (factory generate, CLI-Judge, refiner) but exercises the
REAL path through them -- CLI -> generate -> resolve adapter -> run_refine_loop ->
LoopController -> store -> report. It also pins the load-bearing safety
properties (referee immutability, adapter determinism, fallback attribution)
that the wiring's risks (R-1/R-2/R-3) name.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from loopeng.adapters.base import GenerateResult, Verdict
from loopeng.bindings import LoopDeps
from loopeng.cli import main
from loopeng.memory.store import MemoryStore


def _v(grade):
    return Verdict(grade=grade, score=0.0, dims={"correctness": 30}, safety_ok=True)


class _ScriptedJudge:
    def __init__(self, grades):
        self.verdicts = [_v(g) for g in grades]
        self.calls = 0

    def judge(self, tool_path):
        v = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return v


class _FakeRefiner:
    name = "fake"

    def __init__(self):
        self.last_token_cost = None
        self.last_infra_failure = False
        self.last_fork_cards = []

    def refactor(self, tool_path, brief):
        return "diff"


@pytest.fixture
def env(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    adapter = tmp_path / "adapters" / "x.py"
    adapter.parent.mkdir()
    adapter.write_text("x\n")
    repo = tmp_path / "repo"
    repo.mkdir()

    class FakeFactory:
        def generate(self, target, goal, workdir):
            # Mirror the real adapters: the tool is produced INSIDE workdir
            # (workspace_root), so run_refine_loop's within-workspace jail holds.
            return GenerateResult(tool_path=str(workdir), lane="codebase", ok=True, manifest={})

    # run_refine_loop binds missing_for_refine as a default arg (def-time), so we
    # make the underlying preflight report every tool available instead.
    from loopeng.config import DEPENDENCIES
    from loopeng.preflight import ToolStatus

    monkeypatch.setattr("loopeng.cli.missing_for_lane", lambda lane: [])
    monkeypatch.setattr(
        "loopeng.preflight.preflight",
        lambda: [ToolStatus(d.key, d.label, True, "stub-available") for d in DEPENDENCIES],
    )
    monkeypatch.setattr(
        "loopeng.autonomous.runner._default_factories",
        lambda: {"cli-anything": FakeFactory(), "printing-press": FakeFactory()},
    )
    monkeypatch.setattr(MemoryStore, "default", classmethod(lambda cls: MemoryStore(tmp_path / "db.sqlite")))
    return {"ws": ws, "adapter": adapter, "repo": repo, "tmp": tmp_path, "monkeypatch": monkeypatch}


def _stub_deps(monkeypatch, judge, refiner):
    deps = LoopDeps(judge=judge, refiner=refiner, compounder=None, provider_env_keys=())
    monkeypatch.setattr("loopeng.bindings.build_loop_deps", lambda **k: deps)


def test_run_cli_converges_end_to_end(env):
    _stub_deps(env["monkeypatch"], _ScriptedJudge(["C", "B", "A"]), _FakeRefiner())
    res = CliRunner().invoke(
        main, ["run", str(env["repo"]), "--goal", "g", "--judge-adapter", str(env["adapter"]),
         "--workspace", str(env["ws"])]
    )
    assert res.exit_code == 0, res.output
    assert "converged" in res.output
    assert "Run #1" in res.output
    # The run is recorded + the report renders the before->after trajectory.
    rep = CliRunner().invoke(main, ["report", "1"])
    assert rep.exit_code == 0, rep.output
    assert "C" in rep.output and "A" in rep.output


def test_run_stops_on_budget_without_reaching_a(env):
    # Judge never reaches A; the loop must stop honestly on max-iterations.
    _stub_deps(env["monkeypatch"], _ScriptedJudge(["C", "C", "C", "C"]), _FakeRefiner())
    res = CliRunner().invoke(
        main,
        ["run", str(env["repo"]), "--goal", "g", "--judge-adapter", str(env["adapter"]),
         "--max-iterations", "2", "--workspace", str(env["ws"])],
    )
    assert res.exit_code == 0, res.output
    assert "converged" not in res.output  # stopped, not converged
    assert "Run #1" in res.output


def test_run_rejects_in_jail_adapter(env):
    # Integrity (R-1/R-2): an adapter inside the generated tool is refused at the CLI.
    in_jail = env["ws"] / "cli-judge-adapter.py"
    in_jail.write_text("x\n")
    _stub_deps(env["monkeypatch"], _ScriptedJudge(["A"]), _FakeRefiner())
    res = CliRunner().invoke(
        main, ["run", str(env["repo"]), "--goal", "g", "--judge-adapter", str(in_jail),
         "--workspace", str(env["ws"])]
    )
    assert res.exit_code != 0
    assert "referee must be immutable" in res.output or "inside the generated tool" in res.output


def test_converged_via_fallback_is_attributed(env):
    # Integrity (R-3): when the chain falls through to the LLM, the run names it.
    from loopeng.adapters.llm_refiner import ChainedRefiner

    class _Infra(_FakeRefiner):
        name = "claude"

        def refactor(self, tool_path, brief):
            self.last_infra_failure = True
            return None

    class _Ok(_FakeRefiner):
        name = "groq"

    chain = ChainedRefiner([_Infra(), _Ok()])
    _stub_deps(env["monkeypatch"], _ScriptedJudge(["C", "A"]), chain)
    res = CliRunner().invoke(
        main, ["run", str(env["repo"]), "--goal", "g", "--judge-adapter", str(env["adapter"]),
         "--workspace", str(env["ws"])]
    )
    assert res.exit_code == 0, res.output
    assert "via groq" in res.output  # provenance surfaced, not laundered as claude


def test_resolve_adapter_is_deterministic(env):
    # Integrity (R-2): two candidate adapters -> a stable, documented pick.
    from loopeng.adapters.base import GenerateResult as GR
    from loopeng.adapters.judge import resolve_judge_adapter

    reg = env["tmp"] / "registry"
    reg.mkdir()
    (reg / "mytool.py").write_text("the-one\n")
    (reg / "other.py").write_text("not-this\n")
    gen = GR(tool_path=str(env["ws"]), lane="codebase", ok=True, manifest={"id": "mytool"})
    picks = {resolve_judge_adapter(gen, registry_dir=str(reg)) for _ in range(5)}
    assert len(picks) == 1
    assert picks.pop().endswith("mytool.py")


def test_fleet_run_executes_end_to_end(env):
    import json

    from loopeng.adapters.safety import run_tool

    # A real git repo for worktrees.
    repo = env["tmp"] / "fleetrepo"
    repo.mkdir()
    (repo / "README.md").write_text("x\n")
    run_tool(["git", "-C", str(repo), "init", "-q"])
    run_tool(["git", "-C", str(repo), "config", "user.email", "t@t"])
    run_tool(["git", "-C", str(repo), "config", "user.name", "t"])
    run_tool(["git", "-C", str(repo), "add", "-A"])
    run_tool(["git", "-C", str(repo), "commit", "-q", "-m", "init"])

    _stub_deps(env["monkeypatch"], _ScriptedJudge(["B", "A"]), _FakeRefiner())
    spec = {
        "goal": "g",
        "items": [
            {"key": "a", "target": "https://a.example", "lane": "service"},
            {"key": "b", "target": "https://b.example", "lane": "service", "depends_on": ["a"]},
        ],
    }
    p = env["tmp"] / "spec.json"
    p.write_text(json.dumps(spec))
    res = CliRunner().invoke(
        main,
        ["fleet", "run", str(p), "--repo", str(repo), "--worktrees-root", str(env["tmp"] / "wts"),
         "--judge-adapter", str(env["adapter"])],
    )
    assert res.exit_code == 0, res.output
    assert "Executing fleet" in res.output
    # Both items run end-to-end; converged-but-unconfirmed items escalate for human
    # review (anti-surrender gate), so the fleet parks awaiting_human with item "a"
    # escalated at grade A and its dependent "b" blocked_on_dep. This exercises the
    # full chain: generate -> judge -> gate -> classify -> escalation -> park.
    assert "awaiting_human" in res.output
    assert "escalated" in res.output and "grade=A" in res.output
    assert "blocked_on_dep" in res.output
