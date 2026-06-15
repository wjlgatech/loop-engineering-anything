"""History Compression Engine (U7, R8, R12).

A periodic System-2 pass: consolidate redundant rules/heuristics in the evolving
tool into clean module boundaries, guarding against "big ball of mud" growth.

Distinct from per-iteration fixes (System 1). The compression must be
**grade-neutral-or-better and safe** by construction: it snapshots, runs a
consolidation brief through the refiner, re-judges, and accepts only if the
grade did not drop and safety still holds -- otherwise it rolls back. This
inherits the same regression-rollback discipline as the main loop.

The engine never inspects code to decide what is redundant; it hands the
candidate learnings to the refiner as structured data and lets `/ce-work` do the
consolidation (KTD1/KTD4).
"""

from __future__ import annotations

from dataclasses import dataclass

from .adapters.base import Checkpoint, Judge, RefactorBrief, Refiner, Verdict
from .memory.store import MemoryStore, grade_rank

# Don't bother compressing until there's enough accumulated history to consolidate.
DEFAULT_MIN_LEARNINGS = 3


@dataclass(frozen=True)
class CompressionResult:
    accepted: bool
    before: Verdict
    after: Verdict
    reason: str


class CompressionEngine:
    def __init__(
        self,
        *,
        judge: Judge,
        refiner: Refiner,
        checkpoint: Checkpoint,
        store: MemoryStore,
        min_learnings: int = DEFAULT_MIN_LEARNINGS,
    ):
        self.judge = judge
        self.refiner = refiner
        self.checkpoint = checkpoint
        self.store = store
        self.min_learnings = min_learnings

    def _consolidation_brief(self, learnings: list[dict]) -> RefactorBrief:
        summaries = [l["summary"] for l in learnings]
        return RefactorBrief(
            goal=(
                "Consolidate redundant or overlapping rules/heuristics into clean "
                "module boundaries WITHOUT changing observable behavior. Candidate "
                f"learnings to fold together:\n- " + "\n- ".join(summaries)
            ),
            target_dimensions=["maintainability"],
            failing_fixtures=[],
        )

    def run(self, run_id: int, tool_path: str) -> CompressionResult:
        learnings = self.store.learnings(run_id)
        before = self.judge.judge(tool_path)

        if len(learnings) < self.min_learnings:
            return CompressionResult(False, before, before, "too few learnings to consolidate")

        token = self.checkpoint.snapshot()
        self.refiner.refactor(tool_path, self._consolidation_brief(learnings))
        after = self.judge.judge(tool_path)

        # Accept only if grade-neutral-or-better AND still safe; else roll back.
        if after.safety_ok and grade_rank(after.grade) >= grade_rank(before.grade):
            self.store.record_learning(
                run_id, None, f"compression: consolidated {len(learnings)} learnings, grade held at {after.grade}"
            )
            return CompressionResult(True, before, after, "consolidated; grade held")

        self.checkpoint.restore(token)
        return CompressionResult(False, before, before, "rolled back: compression lowered grade or broke safety")
