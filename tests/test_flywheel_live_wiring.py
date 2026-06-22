"""Live-wiring of the flywheel remainder (plan 2026-06-21), mock-tested.

The actual claude quota run is first-light-gated; here every external call is mocked,
so the wiring is provably correct before the gate opens.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopeng.adapters import spec_refiner as sr
from loopeng.adapters.base import RefactorBrief
from loopeng.adapters.safety import ProcResult
from loopeng.flywheel.ablation import (
    AblationLeg,
    FlywheelProofError,
    record_flywheel_proof,
    run_ablation_pair,
)
from loopeng.flywheel.oracle import SpecOutcome, downstream_oracle
from loopeng.spec import synthesize as syn


def _brief():
    return RefactorBrief(goal="g", target_dimensions=["completeness"], failing_fixtures=["missing:scope_boundaries"],
                         reused_learnings=["add acceptance examples"])


# ----- U8 live editors (mocked subprocess) --------------------------------


def test_synthesize_live_uses_capability_output(tmp_path, monkeypatch):
    monkeypatch.setattr(syn, "run_tool", lambda *a, **k: ProcResult(0, "# spec: real\n## Problem Frame\nP.", ""))
    path = syn.synthesize_spec("build X", str(tmp_path / "s"), live=True)
    assert "# spec: real" in Path(path).read_text()


def test_synthesize_live_falls_back_to_scaffold_on_infra_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(syn, "run_tool", lambda *a, **k: ProcResult(1, "", "boom"))
    path = syn.synthesize_spec("build X", str(tmp_path / "s"), live=True)
    assert "build X" in Path(path).read_text()  # scaffold fallback, not empty


def test_spec_refiner_live_edits_file_and_reports_change(tmp_path, monkeypatch):
    spec = tmp_path / "spec.md"
    spec.write_text("# spec: before\n")

    def fake_run(args, **kw):
        spec.write_text("# spec: after — improved\n## Scope Boundaries\nx\n")  # the "claude" edit
        return ProcResult(0, "done", "")

    monkeypatch.setattr(sr, "run_tool", fake_run)
    r = sr.SpecRefiner(live=True)
    assert r.refactor(str(tmp_path), _brief()) == "spec-edited"
    assert r.last_infra_failure is False


def test_spec_refiner_live_no_change_returns_none(tmp_path, monkeypatch):
    spec = tmp_path / "spec.md"; spec.write_text("# spec: unchanged\n")
    monkeypatch.setattr(sr, "run_tool", lambda *a, **k: ProcResult(0, "noop", ""))
    r = sr.SpecRefiner(live=True)
    assert r.refactor(str(tmp_path), _brief()) is None  # file unchanged -> clean no-change
    assert r.last_infra_failure is False


def test_spec_refiner_live_infra_failure_is_flagged(tmp_path, monkeypatch):
    (tmp_path / "spec.md").write_text("# spec\n")
    monkeypatch.setattr(sr, "run_tool", lambda *a, **k: ProcResult(1, "", "429 throttled"))
    r = sr.SpecRefiner(live=True)
    assert r.refactor(str(tmp_path), _brief()) is None
    assert r.last_infra_failure is True  # retryable transient, not a no-change


def test_spec_refiner_unwired_reports_infra_failure(tmp_path):
    (tmp_path / "spec.md").write_text("# spec\n")
    r = sr.SpecRefiner()  # no editor, not live
    assert r.refactor(str(tmp_path), _brief()) is None
    assert r.last_infra_failure is True


# ----- U6 ablation driver + record-only recorder --------------------------


def test_run_ablation_pair_drives_both_legs():
    calls = []

    def run_leg(disable_reuse):
        calls.append(disable_reuse)
        # reuse ON (disable_reuse=False) converges faster
        return AblationLeg(run_id=10 if not disable_reuse else 11,
                           iterations=2 if not disable_reuse else 5,
                           first_grade="A", converged=True)

    res = run_ablation_pair(run_leg, heldout_seed_hash="seed-1")
    assert calls == [False, True]  # ON leg then OFF leg
    assert res["reuse_helped"] is True and res["delta_iters"] == 3


def test_record_flywheel_proof_writes_only_valid(tmp_path):
    good = run_ablation_pair(
        lambda d: AblationLeg(2 if not d else 3, 2 if not d else 4, "A", True),
        heldout_seed_hash="s",
    )
    dest = tmp_path / "proofs" / "fw.json"
    record_flywheel_proof(good, str(dest))
    assert dest.exists()


def test_record_flywheel_proof_refuses_invalid(tmp_path):
    with pytest.raises(FlywheelProofError):
        record_flywheel_proof({"heldout_seed_hash": "s", "reuse_on": {"run_id": 1}}, str(tmp_path / "x.json"))
    assert not (tmp_path / "x.json").exists()  # nothing written for an invalid proof


# ----- U9 downstream-outcome oracle ---------------------------------------


def test_oracle_supports_when_higher_spec_means_better_tool():
    outcomes = [
        SpecOutcome(spec_score=90, tool_first_grade="A"),
        SpecOutcome(spec_score=70, tool_first_grade="C"),
        SpecOutcome(spec_score=50, tool_first_grade="F"),
    ]
    res = downstream_oracle(outcomes)
    assert res["supports"] is True and res["discordant"] == 0


def test_oracle_does_not_support_when_uncorrelated():
    outcomes = [
        SpecOutcome(spec_score=90, tool_first_grade="F"),  # high spec, bad tool
        SpecOutcome(spec_score=50, tool_first_grade="A"),  # low spec, good tool
    ]
    res = downstream_oracle(outcomes)
    assert res["supports"] is False  # rubric-gaming would land here


def test_oracle_handles_too_little_data():
    assert downstream_oracle([SpecOutcome(80, "A")])["supports"] is False
