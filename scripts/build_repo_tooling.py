"""Prove U4 end-to-end: generate tooling from a real repo KG, grade it, converge.

Pipeline: the committed HarnessX KG summary (U2) -> ToolingSkillFactory (U4)
generates a skill -> ToolingJudge (U3) grades it -> the real LoopController drives
generate→grade→converge. Deterministic (no LLM): the factory produces a faithful
skill, so the controller judges it A and CONVERGES at iteration 0.

Usage: build_repo_tooling.py <kg-summary.json> <out_dir>
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class _NoopRefiner:
    """A distinct maker object (maker != checker) that never edits — used when the
    generated artifact already meets the bar, so the loop converges at iter 0."""

    last_token_cost = None
    last_infra_failure = False
    last_fork_cards: list = []

    def refactor(self, tool_path: str, brief) -> str | None:  # noqa: ARG002
        return None


class _NoopCompounder:
    def compound(self, *a, **k):  # noqa: ANN002, ANN003, ARG002
        return None


def main() -> int:
    from loopeng.adapters.tooling_factory import ToolingSkillFactory
    from loopeng.adapters.tooling_judge import ToolingJudge
    from loopeng.config import Budget
    from loopeng.loop.checkpoint import GitCheckpoint
    from loopeng.loop.controller import LoopController, LoopState
    from loopeng.memory.store import MemoryStore

    kg = sys.argv[1] if len(sys.argv) > 1 else str(REPO / "docs/hub/kg/harnessx/kg-summary.json")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.mkdtemp(prefix="u4-"))
    out.mkdir(parents=True, exist_ok=True)

    # 1. generate
    res = ToolingSkillFactory().generate(kg, "make the repo agent-native", str(out))
    print(f"generated: {res.tool_path}  ({res.logs})")

    # 2. grade (independent U3 referee)
    verdict = ToolingJudge().judge(res.tool_path)
    print(f"grade: {verdict.grade}  score: {verdict.score}  safe: {verdict.safety_ok}")

    # 3. drive the real controller generate→grade→converge (git-init the workspace
    #    so the checkpoint has a repo; a no-op maker means iter-0 convergence on A).
    subprocess.run(["git", "init", "-q"], cwd=res.tool_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=res.tool_path, check=True)
    subprocess.run(["git", "-c", "user.email=u4@local", "-c", "user.name=u4",
                    "commit", "-qm", "generated skill"], cwd=res.tool_path, check=True)

    store = MemoryStore(out / "u4.db")
    run_id = store.create_run(res.tool_path, "tooling", "converge tooling", "2026-07-21T00:00:00Z")
    controller = LoopController(
        judge=ToolingJudge(),
        refiner=_NoopRefiner(),
        compounder=_NoopCompounder(),
        checkpoint=GitCheckpoint(res.tool_path),
        store=store,
        budget=Budget(max_iterations=3),
    )
    outcome = controller.run(run_id, res.tool_path, "converge tooling")
    print(f"controller: {outcome.final_state.name}  grade={outcome.grade}  iterations={outcome.iterations}")
    store.close()

    ok = verdict.grade == "A" and outcome.final_state is LoopState.CONVERGED
    print("RESULT:", "PASS (generate→grade→converge)" if ok else "CHECK")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
