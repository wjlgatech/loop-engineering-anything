"""U7: per-item fleet targets — spec parsing + schema round-trip."""

from __future__ import annotations

import pytest

from loopeng.memory.store import MemoryStore
from loopeng.orchestration.spec import FleetSpecError, materialize_fleet, parse_fleet_spec


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "f.db")
    yield s
    s.close()


def test_parse_item_carries_target_and_goal():
    spec = {
        "goal": "fleet goal",
        "items": [
            {"key": "a", "target": "https://api.example.com", "goal": "item goal"},
            {"key": "b", "target": "./repo", "depends_on": ["a"]},
        ],
    }
    items = parse_fleet_spec(spec)
    a = next(i for i in items if i["key"] == "a")
    assert a["target"] == "https://api.example.com"
    assert a["goal"] == "item goal"
    assert a["depends_on"] == []
    b = next(i for i in items if i["key"] == "b")
    assert b["target"] == "./repo"
    assert b["depends_on"] == ["a"]


def test_parse_missing_target_raises():
    with pytest.raises(FleetSpecError):
        parse_fleet_spec({"items": [{"key": "a"}]})


def test_parse_empty_target_raises():
    with pytest.raises(FleetSpecError):
        parse_fleet_spec({"items": [{"key": "a", "target": ""}]})


def test_materialize_persists_target_goal_lane(store):
    spec = {
        "goal": "fleet goal",
        "items": [
            {"key": "a", "target": "./repo", "lane": "codebase"},
            {"key": "b", "target": "https://x", "goal": "b goal"},
        ],
    }
    fid = materialize_fleet(store, spec["goal"], parse_fleet_spec(spec), "2026-06-18T00:00:00Z")
    by_key = {i.key: i for i in store.fleet_items(fid)}
    assert by_key["a"].target == "./repo"
    assert by_key["a"].lane == "codebase"
    # goal omitted on item "a" -> inherits the fleet goal
    assert by_key["a"].goal == "fleet goal"
    # explicit item goal preserved on "b"
    assert by_key["b"].goal == "b goal"


def test_add_fleet_item_targetless_still_works(store):
    # Backward compatibility: the direct add path (coordinator tests) needs no target.
    fid = store.create_fleet("g", "2026-06-18T00:00:00Z")
    iid = store.add_fleet_item(fid, "solo")
    item = store.fleet_items(fid)[0]
    assert item.id == iid
    assert item.target is None and item.goal is None


def test_parse_invalid_lane_raises():
    with pytest.raises(FleetSpecError):
        parse_fleet_spec({"items": [{"key": "a", "target": "./x", "lane": "frontend"}]})


def test_parse_valid_lane_accepted():
    items = parse_fleet_spec({"items": [{"key": "a", "target": "./x", "lane": "codebase"}]})
    assert items[0]["lane"] == "codebase"
