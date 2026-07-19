"""Drive the software-arch refine-only proof loop live (F -> A, honest).

Mirrors tests/e2e/test_proof_loop.py but for the in-repo software-arch target:
copy the baseline into a git-init'd workspace, grade it (before), let the
free-tier LLM refiner refactor cli.py until the referee converges, and write the
run into the DEFAULT memory store so `loop-anything demo record software-arch
--from <run_id>` can snapshot it. Prints the run_id + before/after proof pack.

Prereqs: cli-judge on PATH, the software-arch suite copied into the cli-judge
checkout, and a free LLM key (GEMINI_API_KEY). Refiner chain is set by the caller
via LOOPENG_REFINER_CHAIN.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    from loopeng.adapters.judge import CLIJudge
    from loopeng.adapters.llm_refiner import FallbackLLMRefiner
    from loopeng.autonomous.runner import run_refine_loop
    from loopeng.config import Budget
    from loopeng.memory.store import MemoryStore
    from loopeng.proof import ProofPack

    baseline = REPO / "demos" / "targets" / "software-arch"
    workspace = Path(tempfile.mkdtemp(prefix="sa-proof-"))
    tool_path = workspace / "software-arch"
    shutil.copytree(baseline, tool_path)
    # A fresh baseline: drop any evidence/output dirs from the committed copy.
    shutil.rmtree(tool_path / "evidence", ignore_errors=True)
    subprocess.run(["git", "init", "-q"], cwd=tool_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tool_path, check=True)
    subprocess.run(["git", "-c", "user.email=proof@local", "-c", "user.name=proof",
                    "commit", "-qm", "baseline"], cwd=tool_path, check=True)

    # The adapter resolves the target CLI from LOOPENG_PROOF_TARGET, so it grades
    # the mutating workspace copy (baseline and every refined iteration).
    os.environ["LOOPENG_PROOF_TARGET"] = str(tool_path)

    adapter = str(REPO / "demos" / "adapters" / "software-arch.py")
    store = MemoryStore.default()
    result = run_refine_loop(
        str(tool_path),
        "make the microservice ops CLI agent-native: non-interactive, JSON output, no crashes",
        judge=CLIJudge(adapter, suite="software-arch"),
        refiner=FallbackLLMRefiner(),
        compounder=None,
        store=store,
        workspace_root=str(workspace),
        budget=Budget(max_iterations=6),
        target_label="software-arch (microservice ops CLI)",
    )

    pack = ProofPack.from_run(store, result.run_id)
    print("=== software-arch proof ===")
    print("run_id:        ", result.run_id)
    print("final_state:   ", result.outcome.final_state)
    print("before_grade:  ", pack.get("before_grade"))
    print("after_grade:   ", pack.get("after_grade"))
    print("iterations:    ", pack.get("iterations"))
    print("improvement:   ", ProofPack.is_improvement(pack))

    # Capture the converged tool as evidence next to the baseline.
    if (tool_path / "cli.py").exists():
        shutil.copy(tool_path / "cli.py", baseline / "evidence" / "after.cli.py")
    store.close()
    return 0 if result.run_id else 1


if __name__ == "__main__":
    sys.exit(main())
