"""End-to-end reference loop against a real target (U8, R11).

This is the one test that exercises the LIVE tools, so it is gated: it runs only
when the factories + judge are installed AND an e2e target is configured. In CI
and on machines without the tools it is skipped, never failed -- a green suite
does not imply this ran. See docs/e2e-runbook.md to run it deliberately.

Prerequisites (all required, else skipped):
  - `cli-judge` and the lane's factory on PATH
  - LOOPENG_E2E_TARGET   e.g. https://api.example.com
  - LOOPENG_E2E_ADAPTER  path to the CLI-Judge tool adapter for the target
  - LOOPENG_E2E_LANE     "service" | "codebase"   (default: service)
"""

from __future__ import annotations

import os
import shutil

import pytest

TARGET = os.environ.get("LOOPENG_E2E_TARGET")
ADAPTER = os.environ.get("LOOPENG_E2E_ADAPTER")
LANE = os.environ.get("LOOPENG_E2E_LANE", "service")
_FACTORY_BIN = {"service": "printing-press", "codebase": "cli-anything"}.get(LANE, "printing-press")

_missing = []
if not TARGET:
    _missing.append("LOOPENG_E2E_TARGET")
if not ADAPTER:
    _missing.append("LOOPENG_E2E_ADAPTER")
if not shutil.which("cli-judge"):
    _missing.append("cli-judge on PATH")
if not shutil.which(_FACTORY_BIN):
    _missing.append(f"{_FACTORY_BIN} on PATH")

pytestmark = pytest.mark.skipif(
    bool(_missing), reason="e2e prerequisites missing: " + ", ".join(_missing)
)


def test_reference_loop_reaches_a_terminal_state(tmp_path):
    from loopeng.adapters.compound_engineering import ClaudeCodeCompounder, ClaudeCodeRefiner
    from loopeng.adapters.judge import CLIJudge
    from loopeng.autonomous.report import render_report
    from loopeng.autonomous.runner import run_loop
    from loopeng.config import Budget, Lane
    from loopeng.loop.controller import LoopState
    from loopeng.memory.store import MemoryStore

    store = MemoryStore(tmp_path / "e2e.db")
    workspace = str(tmp_path / "ws")
    result = run_loop(
        TARGET,
        "make this agent-native and raise it toward Grade A",
        judge=CLIJudge(ADAPTER, strict_unknown=True),
        refiner=ClaudeCodeRefiner(),
        compounder=ClaudeCodeCompounder(workspace),
        store=store,
        budget=Budget(max_iterations=3),
        lane=Lane(LANE),
        workspace_root=workspace,
    )

    assert result.outcome.final_state in {
        LoopState.CONVERGED,
        LoopState.STOPPED,
        LoopState.BLOCKED_SAFETY,
    }
    report = render_report(store, result.run_id)
    assert "Research report" in report
    store.close()
