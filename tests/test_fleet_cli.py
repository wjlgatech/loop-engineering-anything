"""U5 fleet CLI tests (plan-006): run/status/report/escalations."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from loopeng.cli import main
from loopeng.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = MemoryStore(tmp_path / "cli.db")
    monkeypatch.setattr(MemoryStore, "default", classmethod(lambda cls: s))
    yield s
    s.close()


def test_fleet_run_dry_run_materializes_only(store, tmp_path):
    spec = {"goal": "g", "items": [{"key": "a", "target": "./a"}, {"key": "b", "target": "./b", "depends_on": ["a"]}]}
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec))
    res = CliRunner().invoke(main, ["fleet", "run", str(p), "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "created with 2 items" in res.output
    assert "Materialized only" in res.output
    items = store.fleet_items(1)
    assert [i.key for i in items] == ["a", "b"]
    assert items[1].depends_on == ["a"]


def test_fleet_run_executes_by_default(store, tmp_path, monkeypatch):
    spec = {"goal": "g", "items": [{"key": "a", "target": "https://a.example"}, {"key": "b", "target": "https://b.example", "depends_on": ["a"]}]}
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec))

    calls: list[str] = []

    def fake_runner(*, store, fleet_goal, judge_adapter_override, judge_registry, refiner_kind):
        from loopeng.autonomous.runner import RunResult
        from loopeng.loop.controller import LoopOutcome, LoopState

        def _run(item, worktree, upstream):
            calls.append(item.key)
            return RunResult(
                run_id=0,
                outcome=LoopOutcome(LoopState.CONVERGED, "A", "ok", 1, score=0.0, dims={}),
                shippable=True,
            )
        return _run

    # run_fleet creates real git worktrees off --repo, so it must be a git repo.
    from loopeng.adapters.safety import run_tool
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("x\n")
    run_tool(["git", "-C", str(repo), "init", "-q"])
    run_tool(["git", "-C", str(repo), "config", "user.email", "t@t"])
    run_tool(["git", "-C", str(repo), "config", "user.name", "t"])
    run_tool(["git", "-C", str(repo), "add", "-A"])
    run_tool(["git", "-C", str(repo), "commit", "-q", "-m", "init"])

    monkeypatch.setattr("loopeng.cli.missing_for_lane", lambda lane: [])
    monkeypatch.setattr("loopeng.orchestration.coordinator.default_fleet_runner", fake_runner)
    res = CliRunner().invoke(main, ["fleet", "run", str(p), "--repo", str(repo), "--worktrees-root", str(tmp_path / "wts")])
    assert res.exit_code == 0, res.output
    assert "Executing fleet" in res.output
    assert set(calls) == {"a", "b"}  # both items ran in dependency order
    assert "converged" in res.output


def test_fleet_run_preflight_blocks_before_worktrees(store, tmp_path, monkeypatch):
    spec = {"goal": "g", "items": [{"key": "a", "target": "https://a.example"}]}
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec))

    class _Tool:
        label = "CLI-Judge (referee)"
    monkeypatch.setattr("loopeng.cli.missing_for_lane", lambda lane: [_Tool()])
    # If run_fleet were reached it would error differently; assert the preflight message.
    res = CliRunner().invoke(main, ["fleet", "run", str(p)])
    assert res.exit_code != 0
    assert "missing required tools" in res.output
    assert "CLI-Judge" in res.output


def test_fleet_run_rejects_unknown_dependency(store, tmp_path):
    spec = {"items": [{"key": "a", "target": "./a", "depends_on": ["missing"]}]}
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec))
    res = CliRunner().invoke(main, ["fleet", "run", str(p)])
    assert res.exit_code != 0
    assert "unknown item" in res.output
    # No fleet created on a malformed spec.
    assert store.get_fleet(1) is None


def test_fleet_status_unknown_id_is_clean(store):
    res = CliRunner().invoke(main, ["fleet", "status", "999"])
    assert res.exit_code == 0
    assert "No fleet #999" in res.output


def test_fleet_report_and_escalations(store):
    fid = store.create_fleet("g", "2026-06-16T00:00:00Z")
    a = store.add_fleet_item(fid, "a")
    b = store.add_fleet_item(fid, "b")
    for s in ("running", "blocked", "escalated"):
        store.set_item_status(a, s)
    store.record_item_outcome(a, {"grade": "C", "gate_reason": "safety blocked"})
    store.set_item_status(b, "running")
    store.set_item_status(b, "converged")
    store.record_item_outcome(b, {"grade": "A"})

    rep = CliRunner().invoke(main, ["fleet", "report", str(fid)])
    assert rep.exit_code == 0
    assert "escalations: a" in rep.output

    repj = CliRunner().invoke(main, ["fleet", "report", str(fid), "--json"])
    assert '"escalations"' in repj.output

    esc = CliRunner().invoke(main, ["fleet", "escalations", str(fid)])
    assert "safety blocked" in esc.output
