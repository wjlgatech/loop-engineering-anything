"""Fleet spec parsing + materialization (plan-006 U5).

In Phase A the fleet spec is hand-authored (Phase B generates it). A spec is a
dict ``{"goal": "...", "items": [{"key": "a"}, {"key": "b", "depends_on": ["a"]}]}``.
Parsing validates structure and dependency references up front so a malformed
graph fails before any fleet row is created.
"""

from __future__ import annotations


class FleetSpecError(ValueError):
    """A malformed fleet spec (missing key, duplicate key, dangling dependency)."""


def parse_fleet_spec(data: dict) -> list[dict]:
    """Validate a fleet spec and return a normalized item list
    ``[{"key": str, "depends_on": list[str]}, ...]``. Raises ``FleetSpecError``
    on a missing/duplicate key or a dependency referencing an unknown item."""
    if not isinstance(data, dict) or "items" not in data:
        raise FleetSpecError("spec must be an object with an 'items' list")
    raw = data["items"]
    if not isinstance(raw, list) or not raw:
        raise FleetSpecError("'items' must be a non-empty list")

    items: list[dict] = []
    keys: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("key"), str) or not entry["key"]:
            raise FleetSpecError(f"each item needs a non-empty string 'key': {entry!r}")
        key = entry["key"]
        if key in keys:
            raise FleetSpecError(f"duplicate item key: {key!r}")
        keys.add(key)
        # U7: a runnable item needs a target (what the loop runs on). Required and
        # non-empty so the fleet never feeds an arbitrary key into the router.
        target = entry.get("target")
        if not isinstance(target, str) or not target.strip():
            raise FleetSpecError(f"item {key!r} needs a non-empty string 'target'")
        deps = entry.get("depends_on", [])
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            raise FleetSpecError(f"item {key!r} 'depends_on' must be a list of strings")
        goal = entry.get("goal")
        if goal is not None and not isinstance(goal, str):
            raise FleetSpecError(f"item {key!r} 'goal' must be a string when present")
        lane = entry.get("lane")
        if lane is not None and not isinstance(lane, str):
            raise FleetSpecError(f"item {key!r} 'lane' must be a string when present")
        items.append({
            "key": key,
            "target": target,
            "goal": goal,
            "lane": lane,
            "depends_on": list(deps),
        })

    for it in items:
        for dep in it["depends_on"]:
            if dep not in keys:
                raise FleetSpecError(f"item {it['key']!r} depends on unknown item {dep!r}")
    return items


def materialize_fleet(store, goal: str | None, items: list[dict], started: str) -> int:
    """Create a fleet run and its items from a parsed spec; return the fleet id."""
    fleet_id = store.create_fleet(goal, started)
    for it in items:
        store.add_fleet_item(
            fleet_id,
            it["key"],
            depends_on=it["depends_on"],
            target=it.get("target"),
            # An item with no explicit goal inherits the fleet's top-level goal.
            goal=it.get("goal") or goal,
            lane=it.get("lane"),
        )
    return fleet_id
