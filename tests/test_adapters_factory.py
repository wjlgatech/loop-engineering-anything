"""U4 factory adapter tests (mocked subprocess)."""

from __future__ import annotations

import pytest

from loopeng.adapters import cli_anything, printing_press
from loopeng.adapters.safety import ProcResult


def _ok(stdout="built"):
    return ProcResult(0, stdout, "")


def test_printing_press_success(monkeypatch):
    monkeypatch.setattr(printing_press, "run_tool", lambda *a, **k: _ok())
    res = printing_press.PrintingPressFactory().generate("https://api.example.com", workdir="/tmp/wd")
    assert res.ok is True
    assert res.lane == "service"
    assert res.tool_path == "/tmp/wd"


def test_cli_anything_success(monkeypatch):
    monkeypatch.setattr(cli_anything, "run_tool", lambda *a, **k: _ok())
    res = cli_anything.CLIAnythingFactory().generate("/some/repo", workdir="/tmp/wd")
    assert res.ok is True
    assert res.lane == "codebase"


def test_factory_nonzero_exit_is_normalized(monkeypatch):
    monkeypatch.setattr(printing_press, "run_tool", lambda *a, **k: ProcResult(3, "", "boom"))
    res = printing_press.PrintingPressFactory().generate("https://api.example.com")
    assert res.ok is False
    assert "boom" in res.logs


def test_factory_timeout_is_normalized(monkeypatch):
    monkeypatch.setattr(
        printing_press, "run_tool", lambda *a, **k: ProcResult(-1, "", "timed out", timed_out=True)
    )
    res = printing_press.PrintingPressFactory().generate("https://api.example.com")
    assert res.ok is False
    assert res.manifest["timed_out"] is True


def test_factory_rejects_shell_metacharacters(monkeypatch):
    monkeypatch.setattr(printing_press, "run_tool", lambda *a, **k: _ok())
    with pytest.raises(ValueError):
        printing_press.PrintingPressFactory().generate("https://x.com; rm -rf ~")
