"""U7 History Compression Engine tests (grade-neutral-or-better guard)."""

from __future__ import annotations

import pytest

from loopeng.adapters.base import Verdict
from loopeng.compression import CompressionEngine
from loopeng.memory.store import MemoryStore


def v(grade, safety_ok=True, score=80.0):
    return Verdict(grade=grade, score=score, dims={}, safety_ok=safety_ok)


class ScriptedJudge:
    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = 0

    def judge(self, tool_path):
        verdict = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return verdict


class FakeRefiner:
    def __init__(self):
        self.calls = 0

    def refactor(self, tool_path, brief):
        self.calls += 1
        return "diff"


class FakeCheckpoint:
    def __init__(self):
        self.restores = 0

    def snapshot(self):
        return "ckpt"

    def restore(self, token):
        self.restores += 1


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "c.db")
    yield s
    s.close()


def _seed_learnings(store, n):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    for i in range(n):
        store.record_learning(run_id, None, f"learning {i}")
    return run_id


def _engine(store, judge, refiner=None, checkpoint=None, min_learnings=3):
    return (
        CompressionEngine(
            judge=judge,
            refiner=refiner or FakeRefiner(),
            checkpoint=checkpoint or FakeCheckpoint(),
            store=store,
            min_learnings=min_learnings,
        )
    )


def test_compression_accepted_when_grade_held(store):
    run_id = _seed_learnings(store, 3)
    refiner = FakeRefiner()
    eng = _engine(store, ScriptedJudge([v("B"), v("B")]), refiner=refiner)
    result = eng.run(run_id, "tool/")
    assert result.accepted is True
    assert refiner.calls == 1
    # a compression learning was recorded
    assert any("compression" in l["summary"] for l in store.learnings(run_id))


def test_compression_rolled_back_when_grade_drops(store):
    run_id = _seed_learnings(store, 3)
    cp = FakeCheckpoint()
    eng = _engine(store, ScriptedJudge([v("B"), v("C")]), checkpoint=cp)
    result = eng.run(run_id, "tool/")
    assert result.accepted is False
    assert cp.restores == 1
    assert result.after.grade == "B"  # reverted to the pre-compression grade


def test_compression_rolled_back_when_safety_breaks(store):
    run_id = _seed_learnings(store, 3)
    cp = FakeCheckpoint()
    eng = _engine(store, ScriptedJudge([v("B"), v("B", safety_ok=False)]), checkpoint=cp)
    result = eng.run(run_id, "tool/")
    assert result.accepted is False
    assert cp.restores == 1


def test_compression_skipped_when_too_few_learnings(store):
    run_id = _seed_learnings(store, 1)
    refiner = FakeRefiner()
    eng = _engine(store, ScriptedJudge([v("B")]), refiner=refiner, min_learnings=3)
    result = eng.run(run_id, "tool/")
    assert result.accepted is False
    assert refiner.calls == 0  # never refactor without enough to consolidate
