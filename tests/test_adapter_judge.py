"""U5 judge adapter tests (report.json fixtures + safety-cap detection)."""

from __future__ import annotations

import json

from loopeng.adapters import judge as judge_mod
from loopeng.adapters.judge import CLIJudge, parse_report
from loopeng.adapters.safety import ProcResult


def test_grade_a_report_parses_clean():
    data = {"grade": "A", "score": 95, "dimensions": {"correctness": 35, "safety": 20}}
    v = parse_report(data)
    assert v.grade == "A"
    assert v.safety_ok is True
    assert v.dims["correctness"] == 35


def test_safety_gate_flag_caps_regardless_of_score():
    # High score but the safety gate failed -> safety_ok must be False (R3).
    data = {"grade": "C", "score": 88, "safety_gate_failed": True, "dimensions": {"correctness": 35}}
    v = parse_report(data)
    assert v.safety_ok is False


def test_safety_dimension_passed_false():
    data = {"grade": "C", "score": 70, "dimensions": {"safety": {"score": 5, "passed": False}}}
    v = parse_report(data)
    assert v.safety_ok is False


def test_strict_unknown_fails_closed_when_no_safety_signal():
    data = {"grade": "B", "score": 80, "dimensions": {"correctness": 30}}
    assert parse_report(data, strict_unknown=True).safety_ok is False
    assert parse_report(data, strict_unknown=False).safety_ok is True


def test_failing_fixtures_collected():
    data = {"grade": "C", "score": 60, "failing_fixtures": ["pagination_drift"]}
    assert parse_report(data).failing_fixtures == ["pagination_drift"]


def _write_report(tool_dir, payload):
    # The pinned adapter reads report.json from <tool>/.cli-judge (cli-judge --out).
    out = tool_dir / ".cli-judge"
    out.mkdir(exist_ok=True)
    (out / "report.json").write_text(payload)


def test_judge_reads_report_json(monkeypatch, tmp_path):
    _write_report(tmp_path, json.dumps({"grade": "B", "score": 80, "safety_blocker": False, "dimensions": {}}))
    monkeypatch.setattr(judge_mod, "run_tool", lambda *a, **k: ProcResult(0, "Grade: B", ""))
    v = CLIJudge("adapter.py").judge(str(tmp_path))
    assert v.grade == "B"
    assert v.safety_ok is True


def test_judge_missing_report_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(judge_mod, "run_tool", lambda *a, **k: ProcResult(0, "", ""))
    v = CLIJudge("adapter.py").judge(str(tmp_path))
    assert v.safety_ok is False
    assert v.grade == "F"


def test_judge_malformed_report_fails_closed(monkeypatch, tmp_path):
    _write_report(tmp_path, "{not json")
    monkeypatch.setattr(judge_mod, "run_tool", lambda *a, **k: ProcResult(0, "", ""))
    v = CLIJudge("adapter.py").judge(str(tmp_path))
    assert v.safety_ok is False


def test_safety_blocker_field_is_authoritative():
    # The real CLI-Judge safety signal (pinned against a live report.json).
    blocked = parse_report({"grade": "C", "score": 88, "safety_blocker": True, "dimensions": {}})
    assert blocked.safety_ok is False
    ok = parse_report({"grade": "F", "score": 32.6, "safety_blocker": False, "dimensions": {"D1": {"points": 7, "max_points": 30}}})
    assert ok.safety_ok is True
    assert ok.dims["D1"] == 7.0


# ----- resolve_judge_adapter (U3): fail-closed, out-of-jail -----------------

import pytest

from loopeng.adapters.base import GenerateResult
from loopeng.adapters.judge import JudgeAdapterError, resolve_judge_adapter


def _gen(tool_path, manifest=None):
    return GenerateResult(tool_path=str(tool_path), lane="codebase", ok=True, manifest=manifest or {})


def test_resolve_override_outside_jail_returned(tmp_path):
    tool = tmp_path / "tool"; tool.mkdir()
    adapter = tmp_path / "registry" / "a.py"; adapter.parent.mkdir(); adapter.write_text("x\n")
    got = resolve_judge_adapter(_gen(tool), override=str(adapter))
    assert got == str(adapter.resolve()) or got == str(adapter)


def test_resolve_registry_by_manifest_id(tmp_path):
    tool = tmp_path / "tool"; tool.mkdir()
    reg = tmp_path / "registry"; reg.mkdir()
    (reg / "mytool.py").write_text("x\n")
    got = resolve_judge_adapter(_gen(tool, {"id": "mytool"}), registry_dir=str(reg))
    assert got.endswith("mytool.py")


def test_resolve_override_missing_raises(tmp_path):
    tool = tmp_path / "tool"; tool.mkdir()
    with pytest.raises(JudgeAdapterError):
        resolve_judge_adapter(_gen(tool), override=str(tmp_path / "nope.py"))


def test_resolve_rejects_adapter_inside_tool_path(tmp_path):
    # The central safety guard: an adapter inside the maker's write tree is refused.
    tool = tmp_path / "tool"; tool.mkdir()
    inside = tool / "cli-judge-adapter.py"; inside.write_text("x\n")
    with pytest.raises(JudgeAdapterError):
        resolve_judge_adapter(_gen(tool), override=str(inside))


def test_resolve_rejects_manifest_path_escape(tmp_path):
    tool = tmp_path / "tool"; tool.mkdir()
    reg = tmp_path / "registry"; reg.mkdir()
    evil = tmp_path / "evil.py"; evil.write_text("x\n")
    with pytest.raises(JudgeAdapterError):
        resolve_judge_adapter(_gen(tool, {"judge_adapter": str(evil)}), registry_dir=str(reg))


def test_resolve_nothing_found_raises_with_hint(tmp_path):
    tool = tmp_path / "tool"; tool.mkdir()
    reg = tmp_path / "registry"; reg.mkdir()
    with pytest.raises(JudgeAdapterError) as ei:
        resolve_judge_adapter(_gen(tool, {"id": "absent"}), registry_dir=str(reg))
    assert "--judge-adapter" in str(ei.value)


def test_resolve_override_beats_manifest(tmp_path):
    # Deterministic precedence: explicit override wins over a registry candidate.
    tool = tmp_path / "tool"; tool.mkdir()
    reg = tmp_path / "registry"; reg.mkdir()
    (reg / "mytool.py").write_text("registry\n")
    override = tmp_path / "chosen.py"; override.write_text("override\n")
    got = resolve_judge_adapter(
        _gen(tool, {"id": "mytool"}), override=str(override), registry_dir=str(reg)
    )
    assert got.endswith("chosen.py")


# ----- fail-closed on an unexpectedly-shaped report.json (code review) -------

def test_judge_fails_closed_on_wrong_shape_report(tmp_path, monkeypatch):
    tool = tmp_path / "tool"; tool.mkdir()
    out = tool / ".cli-judge"; out.mkdir()
    # Valid JSON, but "dimensions" is a list and score is non-numeric -> would
    # crash parse_report; the judge must return F/not-safe instead. (judge() reads
    # report.json from disk and ignores run_tool's return, so the stub returns None.)
    (out / "report.json").write_text('{"grade": "A+", "score": "high", "dimensions": ["correctness"]}')
    monkeypatch.setattr("loopeng.adapters.judge.run_tool", lambda *a, **k: None)
    v = CLIJudge(adapter_path="x").judge(str(tool))
    assert v.grade == "F"
    assert v.safety_ok is False
