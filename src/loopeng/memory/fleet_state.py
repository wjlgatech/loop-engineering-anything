"""Fleet lifecycle state model (plan-006 U1).

A *fleet run* coordinates multiple loop items under one goal; each item carries an
explicit lifecycle status with a small legal-transition guard, mirroring the
controller's ``LoopState`` discipline. This module is pure data + transitions with
**no store/IO dependency**, so the memory store can import it (and enforce the
guard) without a layering cycle, and the orchestration layer imports the same
enums on top.

Lives in ``memory/`` -- next to the store that persists it -- so the dependency
direction stays orchestration -> memory, never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FleetItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CONVERGED = "converged"
    STOPPED = "stopped"
    BLOCKED = "blocked"  # a BLOCKED_SAFETY worker
    BLOCKED_ON_DEP = "blocked_on_dep"  # a dependency ended non-converged
    ESCALATED = "escalated"  # a high-judgment fork awaiting a human


class FleetRunStatus(str, Enum):
    RUNNING = "running"
    CONVERGED = "converged"  # every item converged
    AWAITING_HUMAN = "awaiting_human"  # PARK: no item ready, escalations open
    STOPPED = "stopped"


# Legal item transitions (source -> allowed targets). Terminal states (converged,
# blocked_on_dep) allow nothing further; escalated re-enters running ONLY on a
# human re-brief (U4 "talk to a worker").
_ITEM_TRANSITIONS: dict[FleetItemStatus, set[FleetItemStatus]] = {
    FleetItemStatus.PENDING: {FleetItemStatus.RUNNING, FleetItemStatus.BLOCKED_ON_DEP},
    FleetItemStatus.RUNNING: {
        FleetItemStatus.CONVERGED,
        FleetItemStatus.STOPPED,
        FleetItemStatus.BLOCKED,
        FleetItemStatus.ESCALATED,
    },
    FleetItemStatus.STOPPED: {FleetItemStatus.ESCALATED},
    FleetItemStatus.BLOCKED: {FleetItemStatus.ESCALATED},
    FleetItemStatus.BLOCKED_ON_DEP: set(),
    FleetItemStatus.ESCALATED: {FleetItemStatus.RUNNING},  # human re-brief
    FleetItemStatus.CONVERGED: set(),
}


class FleetTransitionError(ValueError):
    """An illegal fleet-item status transition (fail-closed, like LoopState)."""


def assert_item_transition(src: FleetItemStatus, dst: FleetItemStatus) -> None:
    """Reject an illegal lifecycle transition. The guard is enforced by the store
    so every persisted status change is legal by construction (U1)."""
    if dst not in _ITEM_TRANSITIONS.get(src, set()):
        raise FleetTransitionError(f"illegal fleet-item transition: {src.value} -> {dst.value}")


@dataclass
class FleetItem:
    id: int
    fleet_id: int
    key: str
    status: FleetItemStatus
    depends_on: list[str] = field(default_factory=list)
    run_id: int | None = None
    outcome: dict | None = None


@dataclass
class FleetRun:
    id: int
    goal: str | None
    status: FleetRunStatus
    started: str
    finished: str | None = None
