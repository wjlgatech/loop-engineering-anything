"""U3 result-schema back-compat + proof-pack field tests.

The proof-pack schema extension must be purely additive: every existing
illustrative fixture still validates, and a fixture carrying a proof block
validates too (R8).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopeng.demos.manifest import ManifestError
from loopeng.demos.result import from_dict

_RESULTS_DIR = Path(__file__).resolve().parents[1] / "demos" / "results"


def _base(**over):
    base = {
        "demo_id": "pr-lifecycle",
        "source": "live_verified",
        "grade_trajectory": ["C", "B", "A"],
        "final_grade": "A",
        "convergence_status": "converged",
    }
    base.update(over)
    return base


def test_all_existing_illustrative_fixtures_still_validate():
    fixtures = sorted(_RESULTS_DIR.glob("*.json"))
    assert fixtures, "expected committed result fixtures"
    for fx in fixtures:
        from_dict(json.loads(fx.read_text()))  # no raise


def test_fixture_with_proof_block_validates():
    r = from_dict(_base(proof={
        "before_grade": "C",
        "after_grade": "A",
        "dim_diff": {"D1": {"before": 10, "after": 28, "delta": 18}},
        "iterations": 4,
        "elapsed_seconds": 38.0,
        "token_cost": None,
        "regression_tests": ["diff-abc"],
        "before_report_ref": "pr-lifecycle.before.json",
        "after_report_ref": "pr-lifecycle.after.json",
    }))
    assert r.verified is True
    assert r.proof["dim_diff"]["D1"]["delta"] == 18


def test_unknown_top_level_field_still_rejected():
    with pytest.raises(ManifestError):
        from_dict(_base(bogus="x"))


def test_unknown_proof_field_rejected():
    with pytest.raises(ManifestError):
        from_dict(_base(proof={"surprise": 1}))
