"""U1 preflight tests (plan U1 Test scenarios)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from loopeng import preflight as pf
from loopeng.cli import main
from loopeng.config import Lane


@pytest.fixture
def all_present(monkeypatch):
    """Make every binary probe resolve and the skill assume-present."""
    monkeypatch.setattr(pf.shutil, "which", lambda name: f"/usr/local/bin/{name}")
    monkeypatch.setenv("LOOPENG_ASSUME_COMPOUND_ENGINEERING", "1")


@pytest.fixture
def none_present(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda name: None)
    monkeypatch.delenv("LOOPENG_ASSUME_COMPOUND_ENGINEERING", raising=False)
    # Point skill detection at a location that does not exist.
    monkeypatch.setattr(pf, "_compound_engineering_locations", lambda: [])


def test_all_four_tools_present(all_present):
    statuses = pf.preflight()
    assert len(statuses) == 4
    assert all(s.available for s in statuses)
    assert {s.key for s in statuses} == {
        "printing-press",
        "cli-anything",
        "cli-judge",
        "compound-engineering",
    }


def test_service_lane_missing_printing_press(monkeypatch, none_present):
    # Everything missing; service lane must report printing-press as a blocker.
    missing = pf.missing_for_lane(Lane.SERVICE)
    keys = {m.key for m in missing}
    assert "printing-press" in keys
    # The codebase factory is NOT required for the service lane.
    assert "cli-anything" not in keys


def test_codebase_lane_missing_cli_anything(none_present):
    missing = pf.missing_for_lane(Lane.CODEBASE)
    keys = {m.key for m in missing}
    assert "cli-anything" in keys
    assert "printing-press" not in keys


def test_judge_and_engine_required_in_both_lanes(none_present):
    for lane in (Lane.SERVICE, Lane.CODEBASE):
        keys = {m.key for m in pf.missing_for_lane(lane)}
        assert "cli-judge" in keys
        assert "compound-engineering" in keys


def test_skill_env_override(monkeypatch):
    monkeypatch.setattr(pf, "_compound_engineering_locations", lambda: [])
    monkeypatch.setenv("LOOPENG_ASSUME_COMPOUND_ENGINEERING", "1")
    ce = next(s for s in pf.preflight() if s.key == "compound-engineering")
    assert ce.available
    assert "LOOPENG_ASSUME_COMPOUND_ENGINEERING" in ce.detail


def test_cli_preflight_json_is_valid_with_one_entry_per_tool(all_present):
    result = CliRunner().invoke(main, ["preflight", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 4
    assert all({"key", "label", "available", "detail"} <= set(e) for e in payload)


def test_cli_preflight_lane_gate_exits_nonzero_when_blocked(none_present):
    result = CliRunner().invoke(main, ["preflight", "--lane", "service"])
    assert result.exit_code == 1
    assert "blocked" in result.output.lower()


def test_refine_keys_claude_requires_compound_engineering():
    keys = pf.required_keys_for_refine("claude")
    assert "cli-judge" in keys
    assert "compound-engineering" in keys
    assert "printing-press" not in keys and "cli-anything" not in keys  # no factory


def test_refine_keys_llm_drops_compound_engineering():
    keys = pf.required_keys_for_refine("llm")
    assert "cli-judge" in keys
    assert "compound-engineering" not in keys  # LLM refiner needs no claude


def test_missing_for_refine_llm_ignores_absent_compound_engineering(none_present):
    blocked = {s.key for s in pf.missing_for_refine(refiner="llm")}
    assert "compound-engineering" not in blocked
    assert "cli-judge" in blocked
