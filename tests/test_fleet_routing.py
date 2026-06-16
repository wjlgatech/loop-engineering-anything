"""U3 feedback-routing tests (plan-006): gather upstream outcomes for dependents."""

from __future__ import annotations

import pytest

from loopeng.memory.store import MemoryStore
from loopeng.orchestration.routing import gather_upstream_outcomes


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "fleet.db")
    yield s
    s.close()


def test_gather_returns_dependency_outcome_summaries(store):
    fid = store.create_fleet(None, "2026-06-16T00:00:00Z")
    a = store.add_fleet_item(fid, "A")
    store.add_fleet_item(fid, "B", depends_on=["A"])
    store.set_item_status(a, "running")
    store.set_item_status(a, "converged")
    store.record_item_outcome(a, {"grade": "A", "final_state": "converged"})
    items = {i.key: i for i in store.fleet_items(fid)}
    out = gather_upstream_outcomes(store, fid, items["B"])
    assert out == [{"item": "A", "grade": "A", "final_state": "converged"}]


def test_gather_empty_without_deps_or_outcome(store):
    fid = store.create_fleet(None, "2026-06-16T00:00:00Z")
    a = store.add_fleet_item(fid, "A")  # no deps
    store.add_fleet_item(fid, "B", depends_on=["A"])  # dep has no outcome yet
    items = {i.key: i for i in store.fleet_items(fid)}
    assert gather_upstream_outcomes(store, fid, items["A"]) == []
    assert gather_upstream_outcomes(store, fid, items["B"]) == []
