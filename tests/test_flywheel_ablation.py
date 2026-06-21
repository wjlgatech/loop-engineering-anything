"""U6 (plan 2026-06-21): ablation mechanics + flywheel-proof integrity."""

from __future__ import annotations

import pytest

from loopeng.flywheel.ablation import (
    AblationLeg,
    FlywheelProofError,
    ablation_result,
    assert_valid_flywheel_proof,
)


def _leg(run_id, iters, grade="A", converged=True):
    return AblationLeg(run_id=run_id, iterations=iters, first_grade=grade, converged=converged)


def test_reuse_helped_when_strictly_fewer_iterations():
    res = ablation_result(_leg(1, 3), _leg(2, 6), heldout_seed_hash="abc")
    assert res["reuse_helped"] is True
    assert res["delta_iters"] == 3


def test_matching_iterations_is_not_a_win():
    res = ablation_result(_leg(1, 5), _leg(2, 5), heldout_seed_hash="abc")
    assert res["reuse_helped"] is False  # matching reuse-OFF fails the premise


def test_non_converged_leg_is_not_a_win():
    res = ablation_result(_leg(1, 3, converged=False), _leg(2, 6), heldout_seed_hash="abc")
    assert res["reuse_helped"] is False


def test_valid_proof_passes():
    res = ablation_result(_leg(1, 3), _leg(2, 6), heldout_seed_hash="seed-1")
    assert_valid_flywheel_proof(res)  # no raise


def test_proof_missing_seed_rejected():
    res = ablation_result(_leg(1, 3), _leg(2, 6), heldout_seed_hash="")
    with pytest.raises(FlywheelProofError):
        assert_valid_flywheel_proof(res)


def test_proof_missing_leg_rejected():
    with pytest.raises(FlywheelProofError):
        assert_valid_flywheel_proof({"heldout_seed_hash": "s", "reuse_on": {"run_id": 1}})


def test_proof_same_run_both_legs_rejected():
    res = ablation_result(_leg(7, 3), _leg(7, 6), heldout_seed_hash="s")
    with pytest.raises(FlywheelProofError):
        assert_valid_flywheel_proof(res)
