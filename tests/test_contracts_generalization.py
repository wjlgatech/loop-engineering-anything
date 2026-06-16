"""U9 contract-generalization tests (plan-004 U9 Test scenarios).

Pins that widening the contracts for domain-generality does not regress the
software loop (R2): the controller still sees a non-null ``grade``, a ``score``
round-trips through the store, legacy ``score=NULL`` rows still read, and the
``Verdict`` shape stays back-compatible.
"""

from __future__ import annotations

import sqlite3

import pytest

from loopeng.adapters.base import Verdict
from loopeng.config import Budget
from loopeng.loop.compound import RecordingCompounder
from loopeng.loop.controller import LoopController, LoopState
from loopeng.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "gen.db")
    yield s
    s.close()


# ----- Verdict back-compat -------------------------------------------------


def test_verdict_constructs_and_compares_identically():
    """Covers back-compat: the (grade, score, dims, safety_ok) shape is unchanged."""
    a = Verdict(grade="B", score=0.82, dims={"correctness": 30}, safety_ok=True)
    b = Verdict(grade="B", score=0.82, dims={"correctness": 30}, safety_ok=True)
    assert a == b
    assert a.grade == "B" and a.score == 0.82


def test_verdict_safety_independent_of_score():
    """Edge: safety_ok=False with a high score still reads as unsafe."""
    bad = Verdict(grade="A", score=0.99, dims={}, safety_ok=False)
    assert bad.safety_ok is False


# ----- score persistence ---------------------------------------------------


def test_score_round_trips_through_store(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    store.record_iteration(run_id, 1, "C", {"safety": 20}, safety_ok=True, score=0.41)
    (it,) = store.iterations(run_id)
    assert it.score == pytest.approx(0.41)
    assert it.grade == "C"  # grade stays non-null alongside the score


def test_legacy_null_score_still_reads(store):
    """A row written without a score (legacy/default) reads back as None, not an error."""
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    store.record_iteration(run_id, 1, "C", {}, safety_ok=True)  # no score arg
    (it,) = store.iterations(run_id)
    assert it.score is None


def test_migrate_adds_score_column_to_preexisting_db(tmp_path):
    """A DB created before the score column gains it via the additive migration."""
    db = tmp_path / "legacy.db"
    raw = sqlite3.connect(db)
    raw.executescript(
        """CREATE TABLE runs (id INTEGER PRIMARY KEY, target TEXT, lane TEXT, goal TEXT,
               status TEXT, final_grade TEXT, started TEXT);
           CREATE TABLE iterations (id INTEGER PRIMARY KEY, run_id INTEGER, n INTEGER,
               grade TEXT NOT NULL, dims_json TEXT NOT NULL,
               failing_fixtures_json TEXT NOT NULL DEFAULT '[]', safety_ok INTEGER NOT NULL,
               token_cost INTEGER, diff_ref TEXT);"""
    )
    raw.commit()
    raw.close()

    store = MemoryStore(db)
    cols = {r["name"] for r in store._conn.execute("PRAGMA table_info(iterations)").fetchall()}
    assert "score" in cols
    store.close()


# ----- controller still sees a non-null grade (R1) -------------------------


def test_controller_runs_against_projected_grade_and_score(store):
    """Covers R1: a domain Verdict carrying a projected grade + score drives the
    controller unchanged -- _record and _finish see a non-null grade as today,
    and the score is persisted on every iteration."""

    class ScriptedJudge:
        def __init__(self, verdicts):
            self.verdicts = verdicts
            self.calls = 0

        def judge(self, tool_path):
            v = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
            self.calls += 1
            return v

    class FakeRefiner:
        def refactor(self, tool_path, brief):
            return "diff"

    class FakeCheckpoint:
        def snapshot(self):
            return "ckpt"

        def restore(self, token):
            pass

    judge = ScriptedJudge(
        [
            Verdict(grade="C", score=0.70, dims={"correctness": 30}, safety_ok=True),
            Verdict(grade="B", score=0.82, dims={"correctness": 30}, safety_ok=True),
            Verdict(grade="A", score=0.95, dims={"correctness": 30}, safety_ok=True),
        ]
    )
    ctrl = LoopController(
        judge=judge,
        refiner=FakeRefiner(),
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_grade="A"),
    )
    run_id = store.create_run("t", "service", "improve", "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "tool/")

    assert outcome.final_state is LoopState.CONVERGED
    assert outcome.grade == "A"  # non-null grade preserved
    its = store.iterations(run_id)
    assert [it.grade for it in its] == ["C", "B", "A"]
    assert [it.score for it in its] == pytest.approx([0.70, 0.82, 0.95])
