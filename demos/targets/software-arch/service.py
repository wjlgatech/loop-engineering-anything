"""Core inventory logic for the software-arch proof target.

Lifted from ``services/example-microservice`` so the ops CLI has a real, in-process
codebase to make agent-native — no HTTP server or replay fixture needed. The loop
refines ``cli.py`` (the ops wrapper); this module is the stable dependency it wraps.
"""

from __future__ import annotations

VERSION = "1.0.0"

_ITEMS: dict[int, dict] = {}
_NEXT_ID = [1]


def create_item(name: str, qty: int = 1) -> dict:
    item = {"id": _NEXT_ID[0], "name": name, "qty": int(qty)}
    _ITEMS[item["id"]] = item
    _NEXT_ID[0] += 1
    return item


def list_items() -> list[dict]:
    return list(_ITEMS.values())


def health() -> dict:
    """The service is healthy when the in-memory store is reachable."""
    return {"status": "ok", "items": len(_ITEMS), "version": VERSION}
