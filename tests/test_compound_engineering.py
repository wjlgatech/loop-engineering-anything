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
    r = ce.ClaudeCodeRefiner()
    assert r.refactor("tool/", _brief()) is None
    # Non-zero exit is an INFRA failure -> retryable (U3).
    assert r.last_infra_failure is True


def test_refiner_returns_none_when_no_changes(monkeypatch):
    def fake_run(args, **kw):
        return ProcResult(0, "" if args[0] == "git" else "done", "")

    monkeypatch.setattr(ce, "run_tool", fake_run)
    r = ce.ClaudeCodeRefiner()
    assert r.refactor("tool/", _brief()) is None
    # A clean run that produced no diff is NOT an infra failure -> never retried.
    assert r.last_infra_failure is False


def test_is_infra_failure_classifies_proc_results():
    from loopeng.adapters.safety import is_infra_failure

    assert is_infra_failure(ProcResult(0, "ok", "")) is False
    assert is_infra_failure(ProcResult(1, "", "boom")) is True  # non-zero exit
    assert is_infra_failure(ProcResult(-1, "", "timed out", timed_out=True)) is True  # timeout
    assert is_infra_failure(ProcResult(127, "", "not found")) is True  # missing exe


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


# ----- U4: Fork-Card emission + parse (plan 2026-06-17) ------------------

_ENVELOPE_WITH_CARDS = (
    '{"usage": {"input_tokens": 10, "output_tokens": 5}, "fork_cards": ['
    '{"id": "f1", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], '
    '"spec_clause": "silent", "chosen_default": "a", "reversibility": "reversible", '
    '"blast_radius": "local"}]}'
)


def test_parse_fork_cards_empty_on_non_json():
    assert ce.parse_fork_cards("done") == []


def test_parse_fork_cards_empty_when_no_key():
    assert ce.parse_fork_cards('{"usage": {"input_tokens": 1}}') == []


def test_parse_fork_cards_maps_well_formed_array():
    cards = ce.parse_fork_cards(_ENVELOPE_WITH_CARDS)
    assert len(cards) == 1
    assert cards[0].id == "f1"
    assert cards[0].chosen_default == "a"


def test_parse_fork_cards_skips_malformed_keeps_valid():
    out = (
        '{"fork_cards": ['
        '{"id": "bad", "options": []}, '  # malformed (empty options) -> skipped
        '{"id": "ok", "options": [{"id": "a"}], "chosen_default": "a"}]}'
    )
    cards = ce.parse_fork_cards(out)
    assert [c.id for c in cards] == ["ok"]


def test_prompt_carries_fork_card_convention():
    prompt = ce.ClaudeCodeRefiner()._build_prompt(_brief())
    assert "fork_cards" in prompt
    assert "do NOT pause to ask" in prompt or "do NOT pause" in prompt


def test_refactor_sets_last_fork_cards_from_single_parse(monkeypatch):
    def fake_run(args, **kw):
        if args[0] == "claude":
            return ProcResult(0, _ENVELOPE_WITH_CARDS, "")
        return ProcResult(0, " 1 file changed", "")

    monkeypatch.setattr(ce, "run_tool", fake_run)
    r = ce.ClaudeCodeRefiner()
    r.refactor("tool/", _brief())
    # Both signals come from the one envelope parse (KTD1).
    assert r.last_token_cost == 15
    assert len(r.last_fork_cards) == 1
    assert r.last_fork_cards[0].id == "f1"


def test_refactor_no_cards_yields_empty_list(monkeypatch):
    def fake_run(args, **kw):
        if args[0] == "claude":
            return ProcResult(0, '{"usage": {"input_tokens": 1}}', "")
        return ProcResult(0, " 1 file changed", "")

    monkeypatch.setattr(ce, "run_tool", fake_run)
    r = ce.ClaudeCodeRefiner()
    r.refactor("tool/", _brief())
    assert r.last_fork_cards == []


def test_compounder_invokes_ce_compound(monkeypatch):
    calls = []
    monkeypatch.setattr(ce, "run_tool", lambda args, **kw: calls.append(args) or ProcResult(0, "", ""))
    ce.ClaudeCodeCompounder("tool/").compound("fixed pagination", regression_test_ref="abc123")
    assert calls[0][0:2] == ["claude", "-p"]
    assert "/ce-compound" in calls[0][2]
    assert "fixed pagination" in calls[0][2]
    assert "abc123" in calls[0][2]
