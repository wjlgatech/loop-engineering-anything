"""U1 fleet lifecycle state tests (plan-006) — the legal-transition guard."""

from __future__ import annotations

import pytest

from loopeng.memory.fleet_state import (
    FleetItemStatus,
    FleetTransitionError,
    assert_item_transition,
)


def test_legal_transitions_pass():
    assert_item_transition(FleetItemStatus.PENDING, FleetItemStatus.RUNNING)
    assert_item_transition(FleetItemStatus.PENDING, FleetItemStatus.BLOCKED_ON_DEP)
    assert_item_transition(FleetItemStatus.RUNNING, FleetItemStatus.CONVERGED)
    assert_item_transition(FleetItemStatus.RUNNING, FleetItemStatus.ESCALATED)  # converged-but-gated
    assert_item_transition(FleetItemStatus.RUNNING, FleetItemStatus.BLOCKED)
    assert_item_transition(FleetItemStatus.STOPPED, FleetItemStatus.ESCALATED)
    assert_item_transition(FleetItemStatus.BLOCKED, FleetItemStatus.ESCALATED)
    assert_item_transition(FleetItemStatus.ESCALATED, FleetItemStatus.RUNNING)  # human re-brief


def test_illegal_transitions_rejected():
    # converged is terminal — the canonical illegal transition.
    with pytest.raises(FleetTransitionError):
        assert_item_transition(FleetItemStatus.CONVERGED, FleetItemStatus.RUNNING)
    # blocked_on_dep is terminal for the item.
    with pytest.raises(FleetTransitionError):
        assert_item_transition(FleetItemStatus.BLOCKED_ON_DEP, FleetItemStatus.RUNNING)
    # cannot jump pending straight to converged (must run first).
    with pytest.raises(FleetTransitionError):
        assert_item_transition(FleetItemStatus.PENDING, FleetItemStatus.CONVERGED)


def test_schema_defaults_match_enum_values():
    # The schema hardcodes status DEFAULTs; they must equal the enum values they
    # represent so a rename can't silently desync new rows from the model.
    import pathlib

    import loopeng.memory as mem
    from loopeng.memory.fleet_state import FleetItemStatus, FleetRunStatus

    schema = (pathlib.Path(mem.__file__).parent / "schema.sql").read_text()
    assert f"status   TEXT NOT NULL DEFAULT '{FleetRunStatus.RUNNING.value}'" in schema
    assert f"status          TEXT NOT NULL DEFAULT '{FleetItemStatus.PENDING.value}'" in schema
