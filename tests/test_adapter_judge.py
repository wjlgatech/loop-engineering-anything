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
