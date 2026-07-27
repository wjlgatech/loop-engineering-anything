"""Drive the vlm-probe refine-only proof loop live (F -> A, honest).

Mirrors scripts/drive_software_arch_proof.py for the vlm-probe target: a naive
human-facing wrap of FM-os `skills/vlm-failure-probe` must be refactored to the
agent-native contract (version/--json/one-shot) PLUS gate honesty (exit 1 on
the failing model). Copies the baseline into a git-init'd workspace, grades it
(before), lets the free-tier LLM refiner refactor cli.py until the referee
converges, and writes the run into the DEFAULT memory store so
`loop-anything demo record vlm-probe --from <run_id>` can snapshot it.

Prereqs: cli-judge importable (repo .venv), suites/vlm-probe.yaml +
fixtures/vlmprobe/ in the cli-judge checkout, FM-os checked out (the probe
engine), and a free LLM key (GEMINI_API_KEY) or local Ollama.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FM_OS_SKILL = Path(
    os.environ.get(
        "VLM_PROBE_SKILL_DIR",
        Path.home() / "Documents/Projects/FM-os/skills/vlm-failure-probe/reference",
    )
)


def main() -> int:
    from loopeng.adapters.judge import CLIJudge
    from loopeng.adapters.llm_refiner import FallbackLLMRefiner
    from loopeng.autonomous.runner import run_refine_loop
    from loopeng.config import Budget
    from loopeng.memory.store import MemoryStore
    from loopeng.proof import ProofPack

    if not (FM_OS_SKILL / "probe_runner.py").exists():
        print(f"FM-os probe engine not found at {FM_OS_SKILL}", file=sys.stderr)
        return 1

    baseline = REPO / "demos" / "targets" / "vlm-probe"
    workspace = Path(tempfile.mkdtemp(prefix="vlmprobe-proof-"))
    tool_path = workspace / "vlm-probe"
    shutil.copytree(baseline, tool_path)
    shutil.rmtree(tool_path / "evidence", ignore_errors=True)
    subprocess.run(["git", "init", "-q"], cwd=tool_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tool_path, check=True)
    subprocess.run(["git", "-c", "user.email=proof@local", "-c", "user.name=proof",
                    "commit", "-qm", "baseline"], cwd=tool_path, check=True)

    # The adapter grades the mutating workspace copy; the target resolves the
    # FM-os probe engine through VLM_PROBE_SKILL_DIR.
    os.environ["LOOPENG_PROOF_TARGET"] = str(tool_path)
    os.environ["VLM_PROBE_SKILL_DIR"] = str(FM_OS_SKILL)

    # Refiner tiers per bindings.py: llm (free chain), claude, or chain (KTD3 default).
    kind = os.environ.get("VLM_PROBE_REFINER", "llm")
    if kind == "llm":
        refiner = FallbackLLMRefiner()
    else:
        from loopeng.adapters.compound_engineering import ClaudeCodeRefiner
        from loopeng.adapters.llm_refiner import ChainedRefiner

        refiner = (
            ClaudeCodeRefiner()
            if kind == "claude"
            else ChainedRefiner([ClaudeCodeRefiner(), FallbackLLMRefiner()])
        )

    adapter = str(REPO / "demos" / "adapters" / "vlm-probe.py")
    store = MemoryStore.default()
    result = run_refine_loop(
        str(tool_path),
        "make the FM-os VLM failure-probe wrap agent-native: `version --json` exits 0; "
        "`probe run --model mock --json` prints one JSON envelope with a 'modes' map and exits 0 "
        "(report-only: exit 0 even when the gate would fail); "
        "`probe gate --model X --json` prints a JSON verdict with 'gate_pass' and exits 1 when the "
        "gate fails (mock) / 0 when it passes (patched) — never prompt, never log on stdout, keep "
        "the real probe engine (probe_runner) wired, never hardcode verdicts. "
        "Engine API (do NOT invent attributes): run_probes(model, spec) returns a plain dict "
        "{mode_id: {'measured': bool, 'score': float|None, 'threshold': float, 'probes': list}}; "
        "gate(results, spec) returns (ok: bool, reasons: list[str]); load_spec() returns the spec.",
        judge=CLIJudge(adapter, suite="vlm-probe"),
        refiner=refiner,
        compounder=None,
        store=store,
        workspace_root=str(workspace),
        budget=Budget(max_iterations=int(os.environ.get("VLM_PROBE_MAX_ITERS", "6"))),
        target_label="vlm-probe (FM-os failure-probe wrap)",
    )

    pack = ProofPack.from_run(store, result.run_id)
    print("=== vlm-probe proof ===")
    print("run_id:        ", result.run_id)
    print("final_state:   ", result.outcome.final_state)
    print("before_grade:  ", pack.get("before_grade"))
    print("after_grade:   ", pack.get("after_grade"))
    print("iterations:    ", pack.get("iterations"))
    print("improvement:   ", ProofPack.is_improvement(pack))

    evidence = baseline / "evidence"
    evidence.mkdir(exist_ok=True)
    if (tool_path / "cli.py").exists():
        shutil.copy(tool_path / "cli.py", evidence / "after.cli.py")
    store.close()
    return 0 if result.run_id else 1


if __name__ == "__main__":
    sys.exit(main())
