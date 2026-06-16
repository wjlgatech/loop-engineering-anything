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


def test_fleet_run_materializes_fleet(store, tmp_path):
    spec = {"goal": "g", "items": [{"key": "a"}, {"key": "b", "depends_on": ["a"]}]}
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec))
    res = CliRunner().invoke(main, ["fleet", "run", str(p)])
    assert res.exit_code == 0, res.output
    assert "created with 2 items" in res.output
    items = store.fleet_items(1)
    assert [i.key for i in items] == ["a", "b"]
    assert items[1].depends_on == ["a"]


def test_fleet_run_rejects_unknown_dependency(store, tmp_path):
    spec = {"items": [{"key": "a", "depends_on": ["missing"]}]}
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
