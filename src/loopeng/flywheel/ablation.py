"""Interleaved-ablation mechanics + proof integrity for the learning-reuse
flywheel (plan 2026-06-21 U6).

The causal claim "reuse makes runs converge faster" is proven by running the SAME
target twice -- reuse ON vs reuse OFF (the loop's ``disable_reuse`` flag forces the
reuse-OFF leg, never a store race) -- with the referee blind to mode, and comparing
iterations-to-converge. This module holds the pure, testable pieces:

  * ``ablation_result`` -- compute the paired delta from two legs' outcomes.
  * ``assert_valid_flywheel_proof`` -- the integrity gate: a result cannot be
    recorded ``live_verified`` unless BOTH legs are present with run_ids and a
    matching held-out seed hash (so an ablation result cannot be fabricated).

The live paired-run driver against real adapters (and recording through the
record-only proof path) is first-light-gated and lives with the e2e suite; these
mechanics are exercised against scripted verdicts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable


class FlywheelProofError(ValueError):
    """A flywheel proof object is incomplete or internally inconsistent."""


@dataclass(frozen=True)
class AblationLeg:
    """One leg of an ablation pair (reuse ON or reuse OFF)."""

    run_id: int
    iterations: int          # iterations-to-converge for this leg
    first_grade: str         # pass@1-attempt grade (first iteration)
    converged: bool


def ablation_result(on: AblationLeg, off: AblationLeg, *, heldout_seed_hash: str) -> dict:
    """Compute the paired ablation outcome. ``reuse_helped`` is True when the reuse-ON
    leg converged AND it did strictly better than reuse-OFF -- either reuse-OFF failed
    to converge at all, or both converged and ON used strictly fewer iterations.
    Matching reuse-OFF (both converged, equal iterations) is a failure of the premise,
    not a pass (U6)."""
    delta_iters = off.iterations - on.iterations  # positive = reuse saved iterations
    reuse_helped = on.converged and (not off.converged or on.iterations < off.iterations)
    return {
        "heldout_seed_hash": heldout_seed_hash,
        "reuse_on": {"run_id": on.run_id, "iterations": on.iterations, "first_grade": on.first_grade},
        "reuse_off": {"run_id": off.run_id, "iterations": off.iterations, "first_grade": off.first_grade},
        "delta_iters": delta_iters,
        "reuse_helped": reuse_helped,
    }


def assert_valid_flywheel_proof(proof: dict) -> None:
    """Integrity gate (U6): refuse to treat an ablation result as proof unless both
    legs are present with run_ids and a shared held-out seed hash. This makes a
    fabricated/half-recorded ablation impossible to pass off as ``live_verified``.
    Raises ``FlywheelProofError`` on any gap."""
    if not isinstance(proof, dict):
        raise FlywheelProofError("flywheel proof must be a mapping")
    seed = proof.get("heldout_seed_hash")
    if not seed:
        raise FlywheelProofError("missing heldout_seed_hash")
    for leg in ("reuse_on", "reuse_off"):
        d = proof.get(leg)
        if not isinstance(d, dict) or d.get("run_id") is None:
            raise FlywheelProofError(f"missing or malformed leg: {leg}")
    if proof["reuse_on"]["run_id"] == proof["reuse_off"]["run_id"]:
        raise FlywheelProofError("both legs reference the same run_id -- not a real pair")


def run_ablation_pair(
    run_leg: Callable[[bool], AblationLeg], *, heldout_seed_hash: str
) -> dict:
    """Drive an interleaved ablation: run the SAME target reuse-ON then reuse-OFF and
    return a validated flywheel proof (U6 live driver). ``run_leg(disable_reuse)`` runs
    one leg and returns its ``AblationLeg`` -- the caller wires it to a real
    ``LoopController`` (with ``disable_reuse`` toggling the reuse-OFF leg) or, for
    tests, a stub. The result is validated before return, so a half-recorded pair
    raises rather than passing as proof."""
    on = run_leg(False)   # reuse ON
    off = run_leg(True)   # reuse OFF (disable_reuse=True)
    result = ablation_result(on, off, heldout_seed_hash=heldout_seed_hash)
    assert_valid_flywheel_proof(result)
    return result


def record_flywheel_proof(proof: dict, dest_path: str) -> str:
    """Record-only write of a flywheel proof: validate FIRST (so only a real, complete
    ablation is ever persisted), then write JSON to ``dest_path``. Mirrors the
    provenance-honesty discipline -- a proof artifact can't be hand-faked into
    existence because ``assert_valid_flywheel_proof`` gates the write."""
    assert_valid_flywheel_proof(proof)
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as fh:
        json.dump(proof, fh, indent=2, sort_keys=True)
    return dest_path
