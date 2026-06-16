"""Automatic feedback routing between fleet items (plan-006 U3).

Deterministic plumbing (no LLM): when the coordinator is about to run an item, it
**pulls** its dependencies' recorded outcomes from the store and passes them as
the worker's ``upstream_context`` (threaded into ``RefactorBrief.upstream_outcomes``
via the U3 seam). This is the cross-item channel — Phase A routes outcome
*summaries*, not code (worktrees branch off HEAD; see the plan's "Fleet item —
definition"). A blocked/stopped upstream routes its reason too, so a dependent is
never run blind.
"""

from __future__ import annotations

from ..memory.fleet_state import FleetItem
from ..memory.store import MemoryStore


def gather_upstream_outcomes(store: MemoryStore, fleet_id: int, item: FleetItem) -> list[dict]:
    """The recorded outcome summaries of ``item``'s direct dependencies, each
    tagged with the upstream item key. Empty when the item has no dependencies or
    none have recorded an outcome yet."""
    by_key = {i.key: i for i in store.fleet_items(fleet_id)}
    outcomes: list[dict] = []
    for dep_key in item.depends_on:
        dep = by_key.get(dep_key)
        if dep is not None and dep.outcome is not None:
            outcomes.append({"item": dep_key, **dep.outcome})
    return outcomes
