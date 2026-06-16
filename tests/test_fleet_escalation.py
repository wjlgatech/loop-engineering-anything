"""U4 fleet escalation tests (plan-006): only high-judgment forks reach a human."""

from __future__ import annotations

import threading

import pytest

from loopeng.adapters.safety import run_tool
from loopeng.autonomous.runner import RunResult
from loopeng.loop.controller import LoopOutcome, LoopState
from loopeng.memory.fleet_state import FleetItemStatus, FleetRunStatus
from loopeng.memory.store import MemoryStore
from loopeng.orchestration.coordinator import run_fleet
from loopeng.orchestration.escalation import classify_with_escalation, rebrief_item


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "fleet.db")
    yield s
    s.close()


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    (d / "README.md").write_text("x\n")
    run_tool(["git", "-C", str(d), "init", "-q"])
    run_tool(["git", "-C", str(d), "config", "user.email", "t@t"])
    run_tool(["git", "-C", str(d), "config", "user.name", "t"])
    run_tool(["git", "-C", str(d), "add", "-A"])
    run_tool(["git", "-C", str(d), "commit", "-q", "-m", "init"])
    return d


def _result(run_id, state=LoopState.CONVERGED, grade="A", shippable=True):
    return RunResult(
        run_id=run_id,
        outcome=LoopOutcome(state, grade, "reason", 2, score=0.0, dims={}),
        shippable=shippable,
    )


# ----- the classifier -----


def test_classify_clean_shippable_converges():
    assert classify_with_escalation(_result(1)) is FleetItemStatus.CONVERGED


def test_classify_converged_but_gated_escalates():
    assert (
        classify_with_escalation(_result(1, shippable=False)) is FleetItemStatus.ESCALATED
    )


def test_classify_blocked_safety_escalates():
    r = _result(1, state=LoopState.BLOCKED_SAFETY, grade="C", shippable=False)
    assert classify_with_escalation(r) is FleetItemStatus.ESCALATED


def test_classify_stopped_escalates():
    r = _result(1, state=LoopState.STOPPED, grade="C", shippable=False)
    assert classify_with_escalation(r) is FleetItemStatus.ESCALATED


# ----- end-to-end with the coordinator -----


def test_blocked_item_escalates_and_parks_fleet(store, repo, tmp_path):
    fid = store.create_fleet(None, "2026-06-16T00:00:00Z")
    store.add_fleet_item(fid, "A")  # will block on safety
    store.add_fleet_item(fid, "B")  # clean, independent
    lock = threading.Lock()
    results = {
        "A": _result(1, state=LoopState.BLOCKED_SAFETY, grade="C", shippable=False),
        "B": _result(2),
    }

    def runner(item, worktree, upstream):
        with lock:
            return results[item.key]

    status = run_fleet(
        store, fid, runner, repo_dir=str(repo), worktrees_root=str(tmp_path / "wts"),
        max_parallel=2, classify=classify_with_escalation,
    )
    items = {i.key: i for i in store.fleet_items(fid)}
    assert items["A"].status is FleetItemStatus.ESCALATED  # never auto-merged
    assert items["B"].status is FleetItemStatus.CONVERGED  # clean item proceeds
    assert status is FleetRunStatus.AWAITING_HUMAN
    assert [i.key for i in store.escalations(fid)] == ["A"]


def test_rebrief_reruns_one_worker_with_human_note(store, repo, tmp_path):
    fid = store.create_fleet(None, "2026-06-16T00:00:00Z")
    store.add_fleet_item(fid, "A")
    # First pass: A is gated (converged but not shippable) -> escalated.
    first = {"A": _result(1, shippable=False)}

    def runner_first(item, worktree, upstream):
        return first[item.key]

    run_fleet(
        store, fid, runner_first, repo_dir=str(repo), worktrees_root=str(tmp_path / "wts"),
        classify=classify_with_escalation,
    )
    item = store.fleet_items(fid)[0]
    assert item.status is FleetItemStatus.ESCALATED
    original_id = item.id

    # Re-brief: a human note is passed, the worker re-runs clean (run_id 99).
    seen = {}

    def runner_rebrief(item, worktree, upstream):
        seen["upstream"] = upstream
        return _result(99, shippable=True)

    result = rebrief_item(
        store, fid, "A", "please widen the timeout", runner_rebrief,
        repo_dir=str(repo), worktrees_root=str(tmp_path / "wts2"),
    )
    assert result is not None
    after = store.fleet_items(fid)[0]
    assert after.id == original_id  # same row, not a new item
    assert after.status is FleetItemStatus.CONVERGED
    assert after.run_id == 99  # run_id replaced in place
    # The human note reached the worker's brief context.
    assert any(u.get("note") == "please widen the timeout" for u in seen["upstream"])


def test_rebrief_rejects_non_escalated_item(store, repo, tmp_path):
    fid = store.create_fleet(None, "2026-06-16T00:00:00Z")
    a = store.add_fleet_item(fid, "A")
    store.set_item_status(a, "running")
    store.set_item_status(a, "converged")

    def runner(item, worktree, upstream):
        return _result(1)

    with pytest.raises(ValueError):
        rebrief_item(
            store, fid, "A", "note", runner,
            repo_dir=str(repo), worktrees_root=str(tmp_path / "wts"),
        )
