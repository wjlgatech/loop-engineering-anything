"""Headless /ce-work and /ce-compound binding tests (P0 #1, mocked subprocess)."""

from __future__ import annotations

from loopeng.adapters import compound_engineering as ce
from loopeng.adapters.base import RefactorBrief
from loopeng.adapters.safety import ProcResult


def _brief():
    return RefactorBrief(goal="raise correctness", target_dimensions=["correctness"], failing_fixtures=["fx1"])


def test_refiner_returns_diff_summary_on_success(monkeypatch):
    calls = []

    def fake_run(args, **kw):
        calls.append(args)
        if args[0] == "claude":
            return ProcResult(0, "done", "")
        return ProcResult(0, " 1 file changed, 3 insertions(+)", "")  # git diff --shortstat

    monkeypatch.setattr(ce, "run_tool", fake_run)
    diff = ce.ClaudeCodeRefiner().refactor("tool/", _brief())
    assert "1 file changed" in diff
    # the /ce-work prompt was passed to claude -p, not interpolated into a shell
    assert calls[0][0:2] == ["claude", "-p"]
    assert "/ce-work" in calls[0][2]


def test_refiner_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(ce, "run_tool", lambda args, **kw: ProcResult(1, "", "boom"))
    assert ce.ClaudeCodeRefiner().refactor("tool/", _brief()) is None


def test_refiner_returns_none_when_no_changes(monkeypatch):
    def fake_run(args, **kw):
        return ProcResult(0, "" if args[0] == "git" else "done", "")

    monkeypatch.setattr(ce, "run_tool", fake_run)
    assert ce.ClaudeCodeRefiner().refactor("tool/", _brief()) is None


def test_parse_token_cost_sums_usage():
    out = '{"result": "ok", "usage": {"input_tokens": 1000, "output_tokens": 500}}'
    assert ce.parse_token_cost(out) == 1500


def test_parse_token_cost_none_when_not_json():
    assert ce.parse_token_cost("done") is None
    assert ce.parse_token_cost('{"result": "ok"}') is None  # no usage block


def test_refiner_captures_last_token_cost(monkeypatch):
    def fake_run(args, **kw):
        if args[0] == "claude":
            return ProcResult(0, '{"usage": {"input_tokens": 200, "output_tokens": 100}}', "")
        return ProcResult(0, " 1 file changed", "")

    monkeypatch.setattr(ce, "run_tool", fake_run)
    r = ce.ClaudeCodeRefiner()
    r.refactor("tool/", _brief())
    assert r.last_token_cost == 300


def test_compounder_invokes_ce_compound(monkeypatch):
    calls = []
    monkeypatch.setattr(ce, "run_tool", lambda args, **kw: calls.append(args) or ProcResult(0, "", ""))
    ce.ClaudeCodeCompounder("tool/").compound("fixed pagination", regression_test_ref="abc123")
    assert calls[0][0:2] == ["claude", "-p"]
    assert "/ce-compound" in calls[0][2]
    assert "fixed pagination" in calls[0][2]
    assert "abc123" in calls[0][2]
