"""End-to-end refine-only proof against a real adopted catalog CLI (U6, R9).

The live half of the catalog-to-proof pipeline. Like the reference-loop e2e it
is GATED: it runs only when the grader + refiner are installed AND a proof
target is configured. In CI and on machines without the tools (or while the
`claude -p` refine quota is closed) it is skipped, never failed -- a green suite
does NOT imply a real before/after proof was produced. See docs/e2e-runbook.md.

Prerequisites (all required, else skipped):
  - `cli-judge` on PATH
  - the refiner: `claude` on PATH (LOOPENG_PROOF_REFINER=claude, default) OR a
    free-tier LLM provider key set (LOOPENG_PROOF_REFINER=llm — no claude quota)
  - LOOPENG_PROOF_DEMO     a demo id with an adapter at demos/adapters/<id>.py
  - LOOPENG_PROOF_BINARY   the adopted tool binary/command to grade + refine
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

DEMO = os.environ.get("LOOPENG_PROOF_DEMO")
BINARY = os.environ.get("LOOPENG_PROOF_BINARY")
REFINER = os.environ.get("LOOPENG_PROOF_REFINER", "claude")
_REPO = Path(__file__).resolve().parents[2]

_missing = []
if not DEMO:
    _missing.append("LOOPENG_PROOF_DEMO")
if not BINARY:
    _missing.append("LOOPENG_PROOF_BINARY")
if not shutil.which("cli-judge"):
    _missing.append("cli-judge on PATH")
if REFINER == "claude" and not shutil.which("claude"):
    _missing.append("claude on PATH (or set LOOPENG_PROOF_REFINER=llm)")
if REFINER == "llm" and not any(
    os.environ.get(k) for k in ("NVIDIA_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY")
):
    _missing.append("a free LLM provider key (NVIDIA_API_KEY/GROQ_API_KEY/GEMINI_API_KEY)")
if DEMO and not (_REPO / "demos" / "adapters" / f"{DEMO}.py").exists():
    _missing.append(f"demos/adapters/{DEMO}.py")

pytestmark = pytest.mark.skipif(
    bool(_missing), reason="proof e2e prerequisites missing: " + ", ".join(_missing)
)


def test_refine_only_proof_produces_a_proof_pack(tmp_path):
    from loopeng.adapters.judge import CLIJudge
    from loopeng.autonomous.runner import run_refine_loop
    from loopeng.config import Budget
    from loopeng.loop.controller import LoopState
    from loopeng.memory.store import MemoryStore
    from loopeng.proof import ProofPack

    workspace = tmp_path / "ws"
    workspace.mkdir()
    # The adopted tool already exists (BINARY); place a marker dir inside the
    # workspace jail to represent the tool path the loop refines.
    tool_path = workspace / "tool"
    tool_path.mkdir()
    adapter = str(_REPO / "demos" / "adapters" / f"{DEMO}.py")

    if REFINER == "llm":
        from loopeng.adapters.llm_refiner import FallbackLLMRefiner
        refiner_impl = FallbackLLMRefiner()
        compounder_impl = None
    else:
        from loopeng.adapters.compound_engineering import ClaudeCodeCompounder, ClaudeCodeRefiner
        refiner_impl = ClaudeCodeRefiner()
        compounder_impl = ClaudeCodeCompounder(str(tool_path))

    store = MemoryStore(tmp_path / "proof.db")
    result = run_refine_loop(
        str(tool_path),
        "raise this catalog CLI toward Grade A",
        judge=CLIJudge(adapter, strict_unknown=True),
        refiner=refiner_impl,
        compounder=compounder_impl,
        store=store,
        workspace_root=str(workspace),
        budget=Budget(max_iterations=3),
    )

    assert result.outcome.final_state in {
        LoopState.CONVERGED,
        LoopState.STOPPED,
        LoopState.BLOCKED_SAFETY,
    }
    pack = ProofPack.from_run(store, result.run_id)
    assert pack["before_grade"] and pack["after_grade"]
    assert pack["iterations"] >= 1
    # Honest: a blocked-safety run is never reported as an improvement.
    if result.outcome.final_state is LoopState.BLOCKED_SAFETY:
        assert ProofPack.is_improvement(pack) is False
    store.close()
