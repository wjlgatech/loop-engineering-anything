"""U5 per-target CLI-Judge adapter tests.

These adapter files import ``cli_judge`` (the grader runtime), which is not a
project dependency and is absent in the default CI image -- so the whole module
skips cleanly when cli_judge is unimportable. When it IS present, each adapter
must define a module-level ``ADAPTER`` that conforms to the contract and skips
cleanly (non-zero exit, no raise) when its binary is absent.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("cli_judge", reason="cli-judge grader not installed (adapters load only at grade time)")

from cli_judge.adapter import Call  # noqa: E402

_ADAPTERS_DIR = Path(__file__).resolve().parents[1] / "demos" / "adapters"
_TARGETS = ["arxiv", "hackernews", "wikipedia"]


def _load(demo_id: str):
    path = _ADAPTERS_DIR / f"{demo_id}.py"
    spec = importlib.util.spec_from_file_location(f"cli_judge_adapter_{demo_id}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("demo_id", _TARGETS)
def test_adapter_defines_conforming_ADAPTER(demo_id):
    mod = _load(demo_id)
    assert hasattr(mod, "ADAPTER"), f"{demo_id}.py must define module-level ADAPTER"
    adapter = mod.ADAPTER
    assert adapter.name == demo_id
    assert callable(adapter.invoke)


@pytest.mark.parametrize("demo_id", _TARGETS)
def test_adapter_skips_cleanly_when_binary_absent(demo_id, monkeypatch):
    monkeypatch.setenv("LOOPENG_PROOF_BINARY", "definitely-not-a-real-binary-xyz")
    mod = _load(demo_id)
    result = mod.ADAPTER.invoke(Call(argv=["--help"]))
    # Missing binary -> captured as exit 127, never raised.
    assert result.exit_code == 127
    assert "failed to launch" in result.stderr


@pytest.mark.parametrize("demo_id", _TARGETS)
def test_adapter_routes_replay_base_url(demo_id, monkeypatch, tmp_path):
    # A trivial fake "binary" that echoes its env so we can assert replay routing.
    script = tmp_path / "echoenv"
    script.write_text("#!/bin/sh\nenv\n")
    script.chmod(0o755)
    monkeypatch.setenv("LOOPENG_PROOF_BINARY", str(script))
    mod = _load(demo_id)
    result = mod.ADAPTER.invoke(Call(argv=[], replay_base_url="http://127.0.0.1:9999"))
    assert result.exit_code == 0
    assert "http://127.0.0.1:9999" in result.stdout  # base-url env was exported
