"""U16 worktree-parallelism tests (plan-004 U16 Test scenarios, R9).

Hermetic + fast: a real temporary git repo + a real temp SQLite DB, no live
tools. Covers:
  - two loops in two worktrees checkpoint/rollback independently;
  - a safety rollback in worktree A leaves worktree B untouched;
  - the concurrency cap is honored and excess targets queue;
  - a crashed worktree run is recorded and cleaned up; siblings continue;
  - concurrent SQLite writes from parallel runs do not corrupt / lose rows.
"""

from __future__ import annotations

import subprocess
import threading
import time

import pytest

from loopeng.autonomous.parallel import ParallelTarget, run_parallel
from loopeng.loop.checkpoint import GitCheckpoint
from loopeng.memory.store import MemoryStore
from loopeng.scheduler import Heartbeat, ScheduledFire


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A real git repo with one committed file, to fan worktrees out of."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "tool.py").write_text("v = 0\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_two_worktrees_checkpoint_and_rollback_independently(repo, tmp_path):
    """Each loop edits + checkpoints + rolls back in its own worktree; neither
    sees the other's diffs."""
    wt_root = tmp_path / "wts"

    def make_run(marker: str):
        def _run(worktree: str) -> str:
            cp = GitCheckpoint(worktree)
            base = cp.snapshot()
            # Each "loop" writes its own content, then rolls back to baseline.
            (pathlike := __import__("pathlib").Path(worktree) / "tool.py").write_text(
                f"v = '{marker}'\n"
            )
            during = pathlike.read_text()
            cp.restore(base)
            after = pathlike.read_text()
            return f"{marker}:{during.strip()}|{after.strip()}"

        return _run

    targets = [
        ParallelTarget(key="alpha", run=make_run("alpha")),
        ParallelTarget(key="beta", run=make_run("beta")),
    ]
    results = run_parallel(targets, repo_dir=str(repo), worktrees_root=str(wt_root), max_parallel=2)

    assert [r.ok for r in results] == [True, True]
    by_key = {r.key: r.value for r in results}
    # Each saw only its own diff during the run, and rolled back to the shared baseline.
    assert by_key["alpha"] == "alpha:v = 'alpha'|v = 0"
    assert by_key["beta"] == "beta:v = 'beta'|v = 0"
    # Worktrees are cleaned up.
    assert not (wt_root / "alpha").exists()
    assert not (wt_root / "beta").exists()


def test_safety_rollback_in_A_does_not_disturb_B(repo, tmp_path):
    """A rollback to baseline in worktree A while B holds a committed change must
    not affect B's working tree."""
    wt_root = tmp_path / "wts"
    import pathlib

    b_started = threading.Event()
    a_rolled_back = threading.Event()

    def run_a(worktree: str) -> str:
        b_started.wait(timeout=5)  # let B establish its own state first
        cp = GitCheckpoint(worktree)
        base = cp.snapshot()
        p = pathlib.Path(worktree) / "tool.py"
        p.write_text("v = 'A-unsafe'\n")
        cp.restore(base)  # safety rollback in A
        a_rolled_back.set()
        return p.read_text().strip()

    def run_b(worktree: str) -> str:
        p = pathlib.Path(worktree) / "tool.py"
        p.write_text("v = 'B-kept'\n")
        cp = GitCheckpoint(worktree)
        cp.snapshot()  # B commits its change
        b_started.set()
        a_rolled_back.wait(timeout=5)  # observe B *after* A rolled back
        return p.read_text().strip()

    results = run_parallel(
        [ParallelTarget("A", run_a), ParallelTarget("B", run_b)],
        repo_dir=str(repo),
        worktrees_root=str(wt_root),
        max_parallel=2,
    )
    by_key = {r.key: r for r in results}
    assert by_key["A"].value == "v = 0"  # A rolled back to baseline
    assert by_key["B"].value == "v = 'B-kept'"  # B untouched by A's rollback


def test_concurrency_cap_is_honored_excess_queue(repo, tmp_path):
    """With max_parallel=2 and 4 targets, never more than 2 run at once; all 4
    eventually complete."""
    wt_root = tmp_path / "wts"
    lock = threading.Lock()
    state = {"active": 0, "peak": 0}

    def _run(_worktree: str) -> int:
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        time.sleep(0.05)
        with lock:
            state["active"] -= 1
        return 1

    targets = [ParallelTarget(key=f"t{i}", run=_run) for i in range(4)]
    results = run_parallel(targets, repo_dir=str(repo), worktrees_root=str(wt_root), max_parallel=2)

    assert len(results) == 4
    assert all(r.ok for r in results)
    assert state["peak"] <= 2  # cap honored; excess queued


def test_crashed_run_is_recorded_and_cleaned_up_siblings_continue(repo, tmp_path):
    """A target whose run raises yields a failed result, its worktree is removed,
    and the healthy siblings still complete."""
    wt_root = tmp_path / "wts"

    def boom(_worktree: str) -> int:
        raise RuntimeError("kaboom")

    def ok(_worktree: str) -> int:
        return 42

    results = run_parallel(
        [ParallelTarget("bad", boom), ParallelTarget("good", ok)],
        repo_dir=str(repo),
        worktrees_root=str(wt_root),
        max_parallel=2,
    )
    by_key = {r.key: r for r in results}
    assert by_key["bad"].ok is False
    assert "kaboom" in (by_key["bad"].error or "")
    assert by_key["good"].ok is True
    assert by_key["good"].value == 42
    # Both worktrees cleaned up regardless of crash.
    assert not (wt_root / "bad").exists()
    assert not (wt_root / "good").exists()


def test_concurrent_sqlite_writes_do_not_corrupt(repo, tmp_path):
    """Parallel runs sharing one MemoryStore each record many iterations; no row
    is lost and no `database is locked` surfaces (serialized writes / WAL)."""
    wt_root = tmp_path / "wts"
    store = MemoryStore(tmp_path / "shared.db")
    try:
        n_targets = 4
        per_target = 25
        run_ids: dict[str, int] = {}
        run_ids_lock = threading.Lock()

        def make_run(name: str):
            def _run(_worktree: str) -> int:
                rid = store.create_run(name, "service", "g", "2026-06-15T00:00:00Z")
                with run_ids_lock:
                    run_ids[name] = rid
                for k in range(per_target):
                    store.record_iteration(rid, k, "B", {"i": k}, safety_ok=True, score=float(k))
                store.finish_run(rid, "CONVERGED", "B")
                return rid

            return _run

        targets = [ParallelTarget(key=f"r{i}", run=make_run(f"r{i}")) for i in range(n_targets)]
        results = run_parallel(targets, repo_dir=str(repo), worktrees_root=str(wt_root), max_parallel=4)

        assert all(r.ok for r in results), [r.error for r in results if not r.ok]
        # Every run recorded exactly `per_target` iterations -- no lost/dup writes.
        for name, rid in run_ids.items():
            its = store.iterations(rid)
            assert len(its) == per_target
            assert [it.n for it in its] == list(range(per_target))
        # All runs are present and finished.
        finished = [r for r in store.list_runs() if r.status == "CONVERGED"]
        assert len(finished) == n_targets
    finally:
        store.close()


def test_duplicate_keys_rejected(repo, tmp_path):
    """Two targets sanitizing to the same worktree slug is a programming error."""
    wt_root = tmp_path / "wts"
    with pytest.raises(ValueError):
        run_parallel(
            [ParallelTarget("a/b", lambda w: 1), ParallelTarget("a-b", lambda w: 1)],
            repo_dir=str(repo),
            worktrees_root=str(wt_root),
        )


def test_empty_targets_is_noop(repo, tmp_path):
    assert run_parallel([], repo_dir=str(repo), worktrees_root=str(tmp_path / "wts")) == []


def test_zero_cap_rejected(repo, tmp_path):
    with pytest.raises(ValueError):
        run_parallel(
            [ParallelTarget("a", lambda w: 1)],
            repo_dir=str(repo),
            worktrees_root=str(tmp_path / "wts"),
            max_parallel=0,
        )


# ----- scheduler fan-out integration (heartbeat -> run_parallel) -------------


def test_heartbeat_tick_parallel_fans_due_targets_across_worktrees(repo, tmp_path):
    """The scheduler fans its due targets out through run_parallel: each runner
    fire lands in an isolated worktree and a run id is recorded as the anchor."""
    store = MemoryStore(tmp_path / "sched.db")
    try:
        seen: dict[str, str] = {}
        seen_lock = threading.Lock()

        def runner(fire: ScheduledFire) -> int:
            # workspace is rebased onto the per-target worktree (isolation).
            with seen_lock:
                seen[fire.target] = fire.workspace
            return store.create_run(fire.target, "service", fire.goal, "2026-06-15T00:00:00Z")

        hb = Heartbeat(store, runner)
        hb.schedule("alpha", interval_seconds=60, goal="ga")
        hb.schedule("beta", interval_seconds=60, goal="gb")

        fired = hb.tick_parallel(
            now=1000.0,
            repo_dir=str(repo),
            worktrees_root=str(tmp_path / "wts"),
            max_parallel=2,
        )

        assert len(fired) == 2
        # Each fire ran in its own (distinct) worktree path, not the default workspace.
        assert seen["alpha"] != seen["beta"]
        assert "alpha" in seen["alpha"] and "beta" in seen["beta"]
        anchors = {e.target: e.last_run_id for e in store.schedules()}
        assert all(v is not None for v in anchors.values())
    finally:
        store.close()


def test_heartbeat_tick_parallel_isolates_a_failing_target(repo, tmp_path):
    """A crashing runner fire is recorded (stamped, no anchor) and does not abort
    the healthy sibling's fire."""
    store = MemoryStore(tmp_path / "sched.db")
    try:

        def runner(fire: ScheduledFire) -> int:
            if fire.target == "bad":
                raise RuntimeError("boom")
            return store.create_run(fire.target, "service", fire.goal, "2026-06-15T00:00:00Z")

        hb = Heartbeat(store, runner)
        hb.schedule("bad", interval_seconds=60)
        hb.schedule("good", interval_seconds=60)

        fired = hb.tick_parallel(
            now=1000.0, repo_dir=str(repo), worktrees_root=str(tmp_path / "wts"), max_parallel=2
        )

        assert len(fired) == 1  # only "good"
        by_target = {e.target: e for e in store.schedules()}
        assert by_target["bad"].last_fired == 1000.0
        assert by_target["bad"].last_run_id is None
        assert by_target["good"].last_run_id is not None
    finally:
        store.close()
