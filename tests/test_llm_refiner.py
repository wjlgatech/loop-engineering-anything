"""Tests for the provider-agnostic fallback-chain LLM refiner (mocked HTTP)."""

from __future__ import annotations

import json

import pytest

from loopeng.adapters import llm_refiner as lr
from loopeng.adapters.base import RefactorBrief


def _brief():
    return RefactorBrief(goal="raise correctness", target_dimensions=["D1"], failing_fixtures=["fx1"])


@pytest.fixture
def tool(tmp_path):
    d = tmp_path / "tool"
    d.mkdir()
    (d / "main.py").write_text("print('v0')\n")
    # a git repo so `git diff --shortstat` works
    from loopeng.adapters.safety import run_tool
    run_tool(["git", "-C", str(d), "init", "-q"])
    run_tool(["git", "-C", str(d), "config", "user.email", "t@t"])
    run_tool(["git", "-C", str(d), "config", "user.name", "t"])
    run_tool(["git", "-C", str(d), "add", "-A"])
    run_tool(["git", "-C", str(d), "commit", "-q", "-m", "init"])
    return d


def _provider(key="groq"):
    return lr.Provider(key, "https://example/v1", "m", "GROQ_API_KEY")


# ----- chain selection ----------------------------------------------------


def test_default_chain_keeps_only_providers_with_keys(monkeypatch):
    for env in ("NVIDIA_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    keys = [p.key for p in lr.default_chain()]
    assert "groq" in keys
    assert "nim" not in keys and "gemini" not in keys
    assert "ollama" in keys  # local rung always kept


def test_chain_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIza_x")
    monkeypatch.setenv("LOOPENG_REFINER_CHAIN", "gemini,ollama")
    keys = [p.key for p in lr.default_chain()]
    assert keys == ["gemini", "ollama"]


# ----- apply + jail -------------------------------------------------------


def test_applies_jailed_full_file_edit(tool, monkeypatch):
    resp = json.dumps({"summary": "fix", "edits": [{"path": "main.py", "content": "print('v1')\n"}]})
    monkeypatch.setattr(lr, "_chat", lambda p, m, *, timeout: resp)
    r = lr.FallbackLLMRefiner(chain=[_provider()])
    ref = r.refactor(str(tool), _brief())
    assert ref is not None
    assert (tool / "main.py").read_text() == "print('v1')\n"


def test_rejects_edit_escaping_workspace(tool, monkeypatch):
    resp = json.dumps({"edits": [{"path": "../escape.py", "content": "x"}]})
    monkeypatch.setattr(lr, "_chat", lambda p, m, *, timeout: resp)
    r = lr.FallbackLLMRefiner(chain=[_provider()])
    ref = r.refactor(str(tool), _brief())
    assert ref is None  # nothing applied
    assert not (tool.parent / "escape.py").exists()


def test_fallback_advances_past_failing_provider(tool, monkeypatch):
    calls = []

    def fake_chat(provider, messages, *, timeout):
        calls.append(provider.key)
        if provider.key == "nim":
            raise OSError("429 throttled")
        return json.dumps({"edits": [{"path": "main.py", "content": "print('v2')\n"}]})

    monkeypatch.setattr(lr, "_chat", fake_chat)
    chain = [lr.Provider("nim", "u", "m", "NVIDIA_API_KEY"), _provider("groq")]
    r = lr.FallbackLLMRefiner(chain=chain)
    ref = r.refactor(str(tool), _brief())
    assert calls == ["nim", "groq"]  # advanced past the throttled rung
    assert r.last_provider == "groq"
    assert ref is not None
    assert r.last_infra_failure is False  # a provider answered -> not an infra failure


def test_whole_chain_failure_returns_none(tool, monkeypatch):
    def boom(provider, messages, *, timeout):
        raise OSError("down")

    monkeypatch.setattr(lr, "_chat", boom)
    r = lr.FallbackLLMRefiner(chain=[_provider(), _provider("gemini")])
    assert r.refactor(str(tool), _brief()) is None
    # A fully-throttled chain is an INFRA failure the controller must retry (U3),
    # not a clean no-change -- this is the bug the fix closes.
    assert r.last_infra_failure is True


def test_unparseable_response_is_not_infra_failure(tool, monkeypatch):
    # A provider answered but the response had no usable edits -> clean no-change,
    # NOT an infra failure (must not be retried as transient).
    monkeypatch.setattr(lr, "_chat", lambda p, m, *, timeout: "I cannot help with that.")
    r = lr.FallbackLLMRefiner(chain=[_provider()])
    assert r.refactor(str(tool), _brief()) is None
    assert r.last_infra_failure is False


def test_parse_edits_tolerates_json_fence():
    summary, edits = lr._parse_edits('```json\n{"summary":"s","edits":[{"path":"a","content":"b"}]}\n```')
    assert summary == "s"
    assert edits == [{"path": "a", "content": "b"}]


# ----- ChainedRefiner (U2) ------------------------------------------------


class _FakeRefiner:
    """A controllable Refiner stub for chain tests."""

    def __init__(self, *, result, infra, token_cost=None, fork_cards=None, name="fake"):
        self._result = result
        self._infra = infra
        self._token_cost = token_cost
        self._fork_cards = fork_cards
        self.name = name
        self.calls = 0
        self.last_token_cost = None
        self.last_infra_failure = False
        # deliberately NO last_fork_cards on some instances to mirror FallbackLLMRefiner

    def refactor(self, tool_path, brief):
        self.calls += 1
        self.last_token_cost = self._token_cost
        self.last_infra_failure = self._infra
        if self._fork_cards is not None:
            self.last_fork_cards = list(self._fork_cards)
        return self._result


def test_chain_returns_first_success_without_calling_rest():
    a = _FakeRefiner(result="diffA", infra=False, token_cost=42, name="claude")
    b = _FakeRefiner(result="diffB", infra=False, name="llm")
    chain = lr.ChainedRefiner([a, b])
    assert chain.refactor("/t", _brief()) == "diffA"
    assert a.calls == 1 and b.calls == 0
    assert chain.last_token_cost == 42
    assert chain.last_refiner == "claude"
    assert chain.last_infra_failure is False


def test_chain_falls_through_on_infra_failure():
    a = _FakeRefiner(result=None, infra=True, token_cost=7, name="claude")
    b = _FakeRefiner(result="diffB", infra=False, name="llm")
    chain = lr.ChainedRefiner([a, b])
    assert chain.refactor("/t", _brief()) == "diffB"
    assert a.calls == 1 and b.calls == 1
    assert chain.last_infra_failure is False  # b succeeded; not an infra failure
    assert chain.last_refiner == "llm"


def test_chain_does_not_fall_through_on_clean_no_change():
    # Claude ran, made no change, but did NOT infra-fail -> stop, do not try LLM.
    a = _FakeRefiner(result=None, infra=False, name="claude")
    b = _FakeRefiner(result="diffB", infra=False, name="llm")
    chain = lr.ChainedRefiner([a, b])
    assert chain.refactor("/t", _brief()) is None
    assert a.calls == 1 and b.calls == 0  # critical: no-change is not a fallback trigger


def test_chain_exhaustion_reports_infra_failure():
    a = _FakeRefiner(result=None, infra=True, name="claude")
    b = _FakeRefiner(result=None, infra=True, name="llm")
    chain = lr.ChainedRefiner([a, b])
    assert chain.refactor("/t", _brief()) is None
    assert a.calls == 1 and b.calls == 1
    assert chain.last_infra_failure is True  # honest exhaustion


def test_chain_resets_fork_cards_across_rungs():
    # Claude emits fork-cards then infra-fails; LLM (no fork_cards attr) runs.
    a = _FakeRefiner(result=None, infra=True, fork_cards=["card1"], name="claude")
    b = _FakeRefiner(result="diffB", infra=False, name="llm")  # no last_fork_cards
    chain = lr.ChainedRefiner([a, b])
    chain.refactor("/t", _brief())
    assert chain.last_fork_cards == []  # not the stale ["card1"] from claude


def test_chain_empty_inner_rejected():
    with pytest.raises(ValueError):
        lr.ChainedRefiner([])


def test_chain_satisfies_refiner_protocol():
    from loopeng.adapters.base import Refiner
    chain = lr.ChainedRefiner([_FakeRefiner(result=None, infra=False)])
    assert isinstance(chain, Refiner)
