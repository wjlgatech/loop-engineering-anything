"""U1: default loop bindings builder."""

from __future__ import annotations

import pytest

from loopeng.adapters.base import Compounder, Judge, Refiner
from loopeng.adapters.compound_engineering import ClaudeCodeRefiner
from loopeng.adapters.judge import CLIJudge
from loopeng.adapters.llm_refiner import ChainedRefiner, FallbackLLMRefiner
from loopeng.bindings import build_loop_deps


def test_chain_kind_builds_chained_refiner_with_compounder():
    deps = build_loop_deps(tool_path="/t", judge_adapter="/reg/a.py", refiner_kind="chain")
    assert isinstance(deps.judge, CLIJudge)
    assert deps.judge.adapter_path == "/reg/a.py"
    assert isinstance(deps.refiner, ChainedRefiner)
    inner = deps.refiner.inner
    assert isinstance(inner[0], ClaudeCodeRefiner) and isinstance(inner[1], FallbackLLMRefiner)
    assert isinstance(deps.compounder, Compounder)
    assert deps.provider_env_keys  # chain advertises provider keys for the credential gate


def test_llm_kind_no_compounder():
    deps = build_loop_deps(tool_path="/t", judge_adapter="/reg/a.py", refiner_kind="llm")
    assert isinstance(deps.refiner, FallbackLLMRefiner)
    assert deps.compounder is None
    assert deps.provider_env_keys


def test_claude_kind_has_compounder_and_no_provider_keys():
    deps = build_loop_deps(tool_path="/t", judge_adapter="/reg/a.py", refiner_kind="claude")
    assert isinstance(deps.refiner, ClaudeCodeRefiner)
    assert isinstance(deps.compounder, Compounder)
    assert deps.provider_env_keys == ()


def test_compound_false_drops_compounder():
    deps = build_loop_deps(tool_path="/t", judge_adapter="/a.py", refiner_kind="claude", compound=False)
    assert deps.compounder is None


def test_unknown_refiner_kind_raises():
    with pytest.raises(ValueError) as ei:
        build_loop_deps(tool_path="/t", judge_adapter="/a.py", refiner_kind="bogus")
    assert "chain" in str(ei.value) and "claude" in str(ei.value) and "llm" in str(ei.value)


def test_deps_satisfy_protocols():
    deps = build_loop_deps(tool_path="/t", judge_adapter="/a.py", refiner_kind="chain")
    assert isinstance(deps.judge, Judge)
    assert isinstance(deps.refiner, Refiner)
