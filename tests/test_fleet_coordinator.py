"""U2 fleet coordinator tests (plan-006): topological waves over run_parallel.

Characterization-first: a no-dependency fleet must behave like today's flat
fan-out (all items in one wave); then dependency ordering, cycle rejection, and
blocked-on-dependency layer on top.
"""

from __future__ import annotations

import threading

import pytest

from loopeng.adapters.safety import run_tool
from loopeng.autonomous.runner import RunResult
from loopeng.loop.controller import LoopOutcome, LoopState
from loopeng.memory.fleet_state import FleetItemStatus, FleetRunStatus
from loopeng.memory.store import MemoryStore
from loopeng.orchestration.coordinator import FleetGraphError, run_fleet


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


def _order_runner(order, lock, results):
    """A runner that records run order (thread-safe) and returns a scripted result."""
    counter = {"n": 0}

    def runner(item, worktree):
        with lock:
            order.append(item.key)
            counter["n"] += 1
            rid = counter["n"]
        return results.get(item.key, _result(rid))

    return runner


def test_no_dependency_fleet_is_flat_fan_out(store, repo, tmp_path):
    # Characterization: three independent items all run in one wave and converge.
    fid = store.create_fleet("g", "2026-06-16T00:00:00Z")
    for k in ("a", "b", "c"):
        store.add_fleet_item(fid, k)
    order, lock = [], threading.Lock()
    status = run_fleet(
        store, fid, _order_runner(order, lock, {}),
        repo_dir=str(repo), worktrees_root=str(tmp_path / "wts"), max_parallel=3,
    )
    assert status is FleetRunStatus.CONVERGED
    assert sorted(order) == ["a", "b", "c"]
    assert all(i.status is FleetItemStatus.CONVERGED for i in store.fleet_items(fid))


def test_diamond_dag_runs_in_topological_waves(store, repo, tmp_path):
    fid = store.create_fleet("g", "2026-06-16T00:00:00Z")
    store.add_fleet_item(fid, "A")
    store.add_fleet_item(fid, "B", depends_on=["A"])
    store.add_fleet_item(fid, "C", depends_on=["A"])
    store.add_fleet_item(fid, "D", depends_on=["B", "C"])
    order, lock = [], threading.Lock()
    status = run_fleet(
        store, fid, _order_runner(order, lock, {}),
        repo_dir=str(repo), worktrees_root=str(tmp_path / "wts"), max_parallel=2,
    )
    assert status is FleetRunStatus.CONVERGED
    assert order[0] == "A"  # root first
    assert order[-1] == "D"  # sink last
    assert set(order[1:3]) == {"B", "C"}  # middle wave, any order


def test_cycle_rejected_before_any_work(store, repo, tmp_path):
    fid = store.create_fleet("g", "2026-06-16T00:00:00Z")
    store.add_fleet_item(fid, "A", depends_on=["B"])
    store.add_fleet_item(fid, "B", depends_on=["A"])
    order, lock = [], threading.Lock()
    with pytest.raises(FleetGraphError):
        run_fleet(
            store, fid, _order_runner(order, lock, {}),
            repo_dir=str(repo), worktrees_root=str(tmp_path / "wts"),
        )
    assert order == []  # no worker ran
    assert all(i.status is FleetItemStatus.PENDING for i in store.fleet_items(fid))


def test_non_converged_dependency_blocks_dependents(store, repo, tmp_path):
    fid = store.create_fleet("g", "2026-06-16T00:00:00Z")
    store.add_fleet_item(fid, "A")
    store.add_fleet_item(fid, "B", depends_on=["A"])  # depends on the failing A
    store.add_fleet_item(fid, "C")  # independent, should still converge
    order, lock = [], threading.Lock()
    results = {"A": _result(1, state=LoopState.STOPPED, grade="C")}
    status = run_fleet(
        store, fid, _order_runner(order, lock, results),
        repo_dir=str(repo), worktrees_root=str(tmp_path / "wts"), max_parallel=2,
    )
    items = {i.key: i for i in store.fleet_items(fid)}
    assert items["A"].status is FleetItemStatus.STOPPED
    assert items["B"].status is FleetItemStatus.BLOCKED_ON_DEP
    assert "B" not in order  # B never ran
    assert items["C"].status is FleetItemStatus.CONVERGED
    assert status is FleetRunStatus.STOPPED  # not all converged, none escalated


def test_escalated_item_parks_the_fleet(store, repo, tmp_path):
    # A classify override (as U4 will provide) sends one item to escalated ->
    # the fleet run ends awaiting_human (PARK), not converged, not a hang.
    fid = store.create_fleet("g", "2026-06-16T00:00:00Z")
    store.add_fleet_item(fid, "A")
    order, lock = [], threading.Lock()

    def classify(result):
        return FleetItemStatus.ESCALATED

    status = run_fleet(
        store, fid, _order_runner(order, lock, {}),
        repo_dir=str(repo), worktrees_root=str(tmp_path / "wts"), classify=classify,
    )
    assert status is FleetRunStatus.AWAITING_HUMAN
    assert store.fleet_items(fid)[0].status is FleetItemStatus.ESCALATED
