"""U7 (plan 2026-06-21): deterministic rubric spec-grader."""

from __future__ import annotations

from loopeng.adapters.spec_judge import SpecJudge
from loopeng.spec.rubric import score_spec

_GOOD_SPEC = """
# feat: thing

## Problem Frame
Users hit X.

## Requirements
- R1 — do the thing.
- R2 — guard the edge.

## Implementation Units

### U1. First
Advances R1. Files: `src/a.py`.
Test scenarios:
- happy path returns Y.

### U2. Second
Advances R2. Files: `src/b.py`.
Test scenarios:
- invalid input rejected.

## Scope Boundaries
Not doing Z.
"""

_NO_TESTS_SPEC = """
# feat: thing
## Problem Frame
P.
## Requirements
- R1 — do it.
## Implementation Units
### U1. Only
Advances R1. Files: `src/a.py`. (coverage intentionally omitted)
## Scope Boundaries
none.
"""


def test_good_spec_scores_high():
    data = score_spec(_GOOD_SPEC)
    assert data["grade"] in ("A", "B")
    assert data["dims"]["completeness"] == 20
    assert data["failing_fixtures"] == [] or "missing" not in " ".join(data["failing_fixtures"])


def test_missing_test_scenarios_drops_completeness():
    data = score_spec(_NO_TESTS_SPEC)
    assert data["dims"]["completeness"] < 20
    assert "units_without_test_scenarios" in data["failing_fixtures"]


def test_dangling_unit_ref_drops_consistency():
    spec = _GOOD_SPEC + "\nSee U9 for details.\n"  # U9 is never defined
    data = score_spec(spec)
    assert data["dims"]["consistency"] < 20
    assert any(f.startswith("dangling_unit_refs") for f in data["failing_fixtures"])


def test_missing_scope_drops_scope_dimension():
    spec = _GOOD_SPEC.replace("## Scope Boundaries\nNot doing Z.", "")
    data = score_spec(spec)
    assert data["dims"]["scope"] < 20
    assert "missing:scope_boundaries" in data["failing_fixtures"]


def test_empty_spec_fails_closed():
    data = score_spec("")
    assert data["grade"] == "F" and data["score"] == 0.0
    assert "empty_or_unreadable_spec" in data["failing_fixtures"]


def test_non_string_fails_closed_no_throw():
    data = score_spec(None)  # type: ignore[arg-type]
    assert data["grade"] == "F"


def test_determinism_same_spec_same_score():
    a = score_spec(_GOOD_SPEC)
    b = score_spec(_GOOD_SPEC)
    assert a == b


def test_feedback_is_dimension_level_and_sanitized():
    data = score_spec(_NO_TESTS_SPEC)
    assert "weakest dimensions" in data["feedback"]
    for bad in ("`", "$", ";"):
        assert bad not in data["feedback"]


# ----- SpecJudge adapter (reads only the artifact, fail-closed) ------------


def test_spec_judge_reads_file(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text(_GOOD_SPEC)
    v = SpecJudge().judge(str(p))
    assert v.grade in ("A", "B") and v.safety_ok is True


def test_spec_judge_reads_dir_spec_md(tmp_path):
    (tmp_path / "spec.md").write_text(_GOOD_SPEC)
    v = SpecJudge().judge(str(tmp_path))
    assert v.grade in ("A", "B")


def test_spec_judge_missing_artifact_fails_closed(tmp_path):
    v = SpecJudge().judge(str(tmp_path / "nope.md"))
    assert v.grade == "F" and v.safety_ok is True


def test_spec_judge_deterministic(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text(_GOOD_SPEC)
    assert SpecJudge().judge(str(p)) == SpecJudge().judge(str(p))
