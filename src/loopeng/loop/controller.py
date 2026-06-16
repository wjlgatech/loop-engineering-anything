"""Loop controller state machine (U6, R3/R4/R5/R7/R12).

Drives judge -> refactor -> re-judge over an already-generated tool until a
terminal state. The controller depends only on the protocols in
``adapters.base`` (Judge, Refiner, Compounder, Checkpoint), so loop dynamics are
fully testable against recorded verdicts -- no real external tool required.

Invariants enforced here:
  - Safety is unbypassable: a safety-failing verdict at any iteration halts in
    BLOCKED_SAFETY, rolls back the offending change, and never compounds or
    ships (KTD5, R3).
  - Regression rollback: a refactor that does not raise the grade is rolled back
    to the prior checkpoint; the prior (better-or-equal) verdict is retained.
  - /ce-compound fires ONLY on an accepted improvement, after the change is kept
    -- never on a transient gain that is later rolled back (ordering fix from
    the doc-review).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum

from ..adapters.base import Checkpoint, Compounder, Judge, Refiner, Verdict
from ..config import Budget
from ..memory.store import MemoryStore
from . import convergence as cv
from .refactor_brief import build_refactor_brief

_log = logging.getLogger(__name__)

# Base backoff for transient (infra) refiner-failure retries (U3); doubles per
# attempt. The wall-clock budget (U4) bounds total retry time.
_TOOL_RETRY_BASE_SECONDS = 2.0


class LoopState(str, Enum):
    ROUTING = "routing"
    GENERATING = "generating"
    JUDGING = "judging"
    REFACTORING = "refactoring"
    COMPRESSING = "compressing"
    CONVERGED = "converged"
    BLOCKED_SAFETY = "blocked_safety"
    STOPPED = "stopped"


# Map a convergence decision kind to its terminal LoopState.
_TERMINAL = {
    cv.CONVERGED: LoopState.CONVERGED,
    cv.BLOCKED_SAFETY: LoopState.BLOCKED_SAFETY,
    cv.STOPPED: LoopState.STOPPED,
}


@dataclass(frozen=True)
class LoopOutcome:
    final_state: LoopState
    grade: str
    reason: str
    iterations: int


class LoopController:
    def __init__(
        self,
        *,
        judge: Judge,
        refiner: Refiner,
        compounder: Compounder,
        checkpoint: Checkpoint,
        store: MemoryStore,
        budget: Budget | None = None,
        compressor=None,
        sleeper=time.sleep,
    ):
        self.judge = judge
        self.refiner = refiner
        self.compounder = compounder
        self.checkpoint = checkpoint
        self.store = store
        self.budget = budget or Budget()
        # Optional History Compression Engine (U7); None = no compression pass.
        self.compressor = compressor
        # Injectable so tests can drive retry backoff without real sleeps (U3).
        self.sleeper = sleeper

    def run(self, run_id: int, tool_path: str, goal: str = "") -> LoopOutcome:
        # Initial grade.
        verdict = self.judge.judge(tool_path)
        n = 1
        self._record(run_id, n, verdict, diff_ref=None)
        tokens_spent = 0
        accepted = 0  # count of kept improvements, for compression cadence
        start = time.monotonic()  # controller owns the clock; evaluate stays pure (U4)
        warned_no_cost = False  # one-time warning when token_budget set but cost unreported

        # Cross-run history (U1): fixtures that have failed across prior runs of
        # THIS target. Scoped to the target so an unrelated target's history never
        # leaks in. Computed once -- prior-run history does not change mid-run.
        run = self.store.get_run(run_id)
        recurring_fixtures = (
            [fx for fx, _ in self.store.recurring_failures(target=run.target)]
            if run is not None
            else []
        )

        while True:
            plateaued = self.store.is_plateaued(
                run_id,
                self.budget.plateau_patience,
                on_score=self.budget.target_score is not None,
            )
            decision = cv.evaluate(
                verdict,
                self.budget,
                iterations_done=n,
                plateaued=plateaued,
                tokens_spent=tokens_spent,
                elapsed_seconds=time.monotonic() - start,
            )
            if decision.kind != cv.CONTINUE:
                return self._finish(run_id, decision, verdict, n)

            # --- REFACTORING ---
            token = self.checkpoint.snapshot()
            brief = build_refactor_brief(verdict, goal, recurring_failures=recurring_fixtures)
            diff_ref = self._refactor_with_retry(tool_path, brief)

            # Cost accounting (U4): thread the refiner's reported per-refactor cost
            # into the budget gate, protocol-bound (getattr tolerates refiners that
            # don't implement it). A refiner that reports no cost cannot advance the
            # token gate -- warn once if a token_budget was set against it.
            cost = getattr(self.refiner, "last_token_cost", None)
            if cost is not None:
                tokens_spent += cost
            elif self.budget.token_budget is not None and not warned_no_cost:
                warned_no_cost = True
                _log.warning(
                    "token_budget=%s is set but the refiner reports no token cost; "
                    "the token gate cannot fire -- relying on max_wall_seconds=%s.",
                    self.budget.token_budget,
                    self.budget.max_wall_seconds,
                )

            new_verdict = self.judge.judge(tool_path)
            n += 1
            self._record(run_id, n, new_verdict, diff_ref=diff_ref, token_cost=cost)

            # Safety failure introduced by the refactor: roll back, halt, no ship.
            if not new_verdict.safety_ok:
                self.checkpoint.restore(token)
                return self._finish(
                    run_id,
                    cv.Decision(cv.BLOCKED_SAFETY, "refactor introduced a safety failure"),
                    new_verdict,
                    n,
                )

            if cv.is_improvement(verdict, new_verdict, self.budget):
                # Improvement accepted and kept -> compound (never on rollback).
                self.compounder.compound(
                    f"iteration {n}: grade {verdict.grade} -> {new_verdict.grade} "
                    f"by targeting {brief.target_dimensions[:2]}",
                    regression_test_ref=diff_ref,
                )
                verdict = new_verdict
                accepted += 1
                # Periodic System-2 compression pass (U7), on accepted-fix cadence.
                if self.compressor is not None and accepted % self.budget.compression_interval == 0:
                    result = self.compressor.run(run_id, tool_path)
                    verdict = result.after
                    n += 1
                    self._record(run_id, n, verdict, diff_ref="compression")
            else:
                # Regression or no gain -> roll back; keep the prior verdict.
                self.checkpoint.restore(token)

    # ----- helpers --------------------------------------------------------

    def _refactor_with_retry(self, tool_path: str, brief) -> str | None:
        """Run the refiner, retrying only a *transient infra* failure (U3).

        Infra failure (timeout / non-zero exit / missing executable) is surfaced
        by the refiner's ``last_infra_failure`` flag and retried with bounded
        exponential backoff. A clean no-change result is NOT retried (it returns
        immediately and the loop rolls back as usual). Safety is detected by the
        judge *after* this returns, so a safety failure can never enter retry.
        Retries do not increment the iteration count; wall time is bounded by the
        wall-clock budget (U4).
        """
        attempt = 0
        while True:
            diff_ref = self.refiner.refactor(tool_path, brief)
            if not getattr(self.refiner, "last_infra_failure", False):
                return diff_ref
            if attempt >= self.budget.max_tool_retries:
                return diff_ref  # exhausted -> fall through to normal no-change handling
            attempt += 1
            self.sleeper(_TOOL_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))

    def _record(
        self, run_id: int, n: int, verdict: Verdict, diff_ref: str | None, token_cost: int | None = None
    ) -> None:
        self.store.record_iteration(
            run_id,
            n,
            verdict.grade,
            verdict.dims,
            safety_ok=verdict.safety_ok,
            failing_fixtures=verdict.failing_fixtures,
            token_cost=token_cost,
            diff_ref=diff_ref,
            score=verdict.score,
        )

    def _finish(self, run_id: int, decision: cv.Decision, verdict: Verdict, n: int) -> LoopOutcome:
        state = _TERMINAL[decision.kind]
        self.store.finish_run(run_id, state.value, verdict.grade)
        return LoopOutcome(final_state=state, grade=verdict.grade, reason=decision.reason, iterations=n)
