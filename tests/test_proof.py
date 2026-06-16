"""U3 proof-pack tests: ProofPack.from_run + StoreBackedCompounder."""

from __future__ import annotations

import pytest

from loopeng.proof import ProofPack, StoreBackedCompounder
from loopeng.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "proof.db")
    yield s
    s.close()


def _run_with(store, grades_dims, *, status="converged", started="2026-06-15T00:00:00+00:00",
              finished="2026-06-15T00:00:38+00:00"):
    run_id = store.create_run("adopted-tool", "service", "improve it", started)
    for n, (grade, dims) in enumerate(grades_dims, start=1):
        store.record_iteration(run_id, n, grade, dims, safety_ok=True)
    store.finish_run(run_id, status, grades_dims[-1][0])
    if finished:
        store.record_finished(run_id, finished)
    return run_id


def test_proof_pack_computes_before_after_and_dim_diff(store):
    run_id = _run_with(store, [
        ("C", {"D1": 10, "D2": 12}),
        ("A", {"D1": 28, "D2": 12}),
    ])
    pack = ProofPack.from_run(store, run_id)
    assert pack["before_grade"] == "C"
    assert pack["after_grade"] == "A"
    assert pack["iterations"] == 2
    assert pack["dim_diff"]["D1"] == {"before": 10, "after": 28, "delta": 18}
    assert pack["dim_diff"]["D2"]["delta"] == 0
    assert pack["elapsed_seconds"] == 38.0
    assert ProofPack.is_improvement(pack) is True


def test_proof_pack_omits_token_cost_when_unwired(store):
    run_id = _run_with(store, [("C", {"D1": 10}), ("B", {"D1": 18})])
    pack = ProofPack.from_run(store, run_id)
    assert "token_cost" not in pack  # never a placeholder when no source recorded


def test_proof_pack_surfaces_token_cost_when_present(store):
    run_id = store.create_run("t", "service", "g", "2026-06-15T00:00:00+00:00")
    store.record_iteration(run_id, 1, "C", {"D1": 10}, safety_ok=True)
    store.record_iteration(run_id, 2, "A", {"D1": 28}, safety_ok=True, token_cost=1500)
    store.finish_run(run_id, "converged", "A")
    pack = ProofPack.from_run(store, run_id)
    assert pack["token_cost"] == 1500


def test_proof_pack_blocked_safety_is_not_an_improvement(store):
    run_id = _run_with(store, [("C", {"D1": 10}), ("C", {"D1": 10})], status="blocked_safety")
    pack = ProofPack.from_run(store, run_id)
    assert pack["convergence_status"] == "blocked_safety"
    assert ProofPack.is_improvement(pack) is False


def test_proof_pack_no_gain_is_not_an_improvement(store):
    run_id = _run_with(store, [("B", {"D1": 18}), ("B", {"D1": 18})], status="stopped")
    pack = ProofPack.from_run(store, run_id)
    assert ProofPack.is_improvement(pack) is False


def test_store_backed_compounder_records_learning_and_delegates(store):
    run_id = store.create_run("t", "service", "g", "2026-06-15T00:00:00+00:00")
    store.record_iteration(run_id, 1, "C", {"D1": 10}, safety_ok=True)

    class Inner:
        def __init__(self):
            self.calls = []

        def compound(self, summary, *, regression_test_ref=None):
            self.calls.append((summary, regression_test_ref))

    inner = Inner()
    comp = StoreBackedCompounder(store, run_id, inner=inner)
    comp.compound("fixed pagination", regression_test_ref="diff-abc")

    learnings = store.learnings(run_id)
    assert len(learnings) == 1
    assert learnings[0]["regression_test_ref"] == "diff-abc"
    assert inner.calls == [("fixed pagination", "diff-abc")]
    # the proof pack now surfaces the regression test
    store.finish_run(run_id, "converged", "C")
    pack = ProofPack.from_run(store, run_id)
    assert pack["regression_tests"] == ["diff-abc"]


def test_proof_pack_raises_on_unknown_run(store):
    with pytest.raises(ValueError, match="no run"):
        ProofPack.from_run(store, 999)
