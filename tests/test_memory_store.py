"""U2 memory store tests (plan U2 Test scenarios)."""

from __future__ import annotations

import pytest

from loopeng.memory.store import MemoryStore, grade_rank


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "test.db")
    yield s
    s.close()


def test_record_run_with_iterations_returns_ordered(store):
    run_id = store.create_run("https://api.example.com", "service", "improve it", "2026-06-15T00:00:00Z")
    store.record_iteration(run_id, 1, "C", {"safety": 20}, safety_ok=True)
    store.record_iteration(run_id, 2, "B", {"safety": 20}, safety_ok=True)
    store.record_iteration(run_id, 3, "A", {"safety": 20}, safety_ok=True)
    its = store.iterations(run_id)
    assert [it.n for it in its] == [1, 2, 3]
    assert store.grade_trajectory(run_id) == ["C", "B", "A"]


def test_grade_rank_ordering():
    assert grade_rank("A") > grade_rank("B") > grade_rank("C") > grade_rank("F")
    assert grade_rank("Z") == -1


def test_plateau_true_when_no_gain(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    for n, g in enumerate(["C", "B", "B", "B", "B"], start=1):
        store.record_iteration(run_id, n, g, {}, safety_ok=True)
    # last 3 (B,B,B) do not beat the best-before (max of C,B = B) -> plateau.
    assert store.is_plateaued(run_id, patience=3) is True


def test_plateau_false_when_still_improving(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    for n, g in enumerate(["C", "C", "B", "A"], start=1):
        store.record_iteration(run_id, n, g, {}, safety_ok=True)
    # last 3 (C,B,A) beat best-before (C) -> not plateaued.
    assert store.is_plateaued(run_id, patience=3) is False


def test_plateau_false_when_fewer_than_patience(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    store.record_iteration(run_id, 1, "C", {}, safety_ok=True)
    store.record_iteration(run_id, 2, "C", {}, safety_ok=True)
    assert store.is_plateaued(run_id, patience=3) is False


def test_recurring_failures_join_across_runs(store):
    r1 = store.create_run("t1", "service", None, "2026-06-15T00:00:00Z")
    r2 = store.create_run("t2", "service", None, "2026-06-15T00:00:00Z")
    store.record_iteration(r1, 1, "C", {}, safety_ok=True, failing_fixtures=["pagination_drift", "token_misclass"])
    store.record_iteration(r2, 1, "C", {}, safety_ok=True, failing_fixtures=["pagination_drift"])
    recurring = store.recurring_failures(min_runs=2)
    assert recurring == [("pagination_drift", 2)]


def test_finish_run_and_list(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    store.finish_run(run_id, "converged", "A")
    run = store.get_run(run_id)
    assert run.status == "converged"
    assert run.final_grade == "A"
    assert store.list_runs()[0].id == run_id


def test_learnings_recorded(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    it = store.record_iteration(run_id, 1, "B", {}, safety_ok=True)
    store.record_learning(run_id, it, "fixed pagination drift", "tests/test_pagination.py")
    learns = store.learnings(run_id)
    assert len(learns) == 1
    assert learns[0]["summary"] == "fixed pagination drift"
