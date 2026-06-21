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
from dataclasses import dataclass, field
from enum import Enum

from ..adapters.base import Checkpoint, Compounder, Judge, ReflectionContext, Refiner, Verdict
from ..config import Budget
from ..memory.store import MemoryStore, grade_rank
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
    # Final verdict signal, carried so the verification gate can compose a legible
    # firing reason (which dimension/score was borderline) without re-judging (U5).
    score: float = 0.0
    dims: dict = field(default_factory=dict)
    # Fork-Cards emitted across the run (plan 2026-06-17 U6): build decisions the
    # spec did not determine, surfaced for end-review. Defaulted to honor KTD1
    # (LoopOutcome additions stay nullable/defaulted).
    fork_cards: list = field(default_factory=list)


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
        resolver=None,
        sleeper=time.sleep,
        upstream_context=None,
        reuse_cross_target=False,
        disable_reuse=False,
    ):
        self.judge = judge
        self.refiner = refiner
        self.compounder = compounder
        self.checkpoint = checkpoint
        self.store = store
        self.budget = budget or Budget()
        # Optional History Compression Engine (U7); None = no compression pass.
        self.compressor = compressor
        # Optional Fork-Card resolver (plan 2026-06-17 U6); None = cards are
        # recorded + surfaced but not resolved/reversed (backward compatible).
        self.resolver = resolver
        # Injectable so tests can drive retry backoff without real sleeps (plan-005 U3).
        self.sleeper = sleeper
        # Upstream fleet-item outcomes routed into this run's briefs (plan-006 U3).
        # Empty/None for a non-fleet single-target run -> identical to prior behavior.
        self.upstream_context = list(upstream_context or [])
        # Learning-reuse flywheel knobs (plan 2026-06-21). ``reuse_cross_target``
        # opts into same-lane other-target reuse (U4; off by default, gated on a
        # positive same-target signal). ``disable_reuse`` suppresses reuse entirely
        # for an ablation's reuse-OFF leg (U6) -- forced empty, not a store race.
        self.reuse_cross_target = reuse_cross_target
        self.disable_reuse = disable_reuse

    def run(self, run_id: int, tool_path: str, goal: str = "") -> LoopOutcome:
        # Initial grade.
        verdict = self.judge.judge(tool_path)
        n = 1
        self._record(run_id, n, verdict, diff_ref=None)
        # Fork-Cards collected across this run, surfaced on the outcome (U6).
        self._collected_fork_cards: list = []
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
        # Learning-reuse flywheel (plan 2026-06-21 U3/U4): compounded learnings from
        # PRIOR runs of this target (and, when opted in, same-lane other targets),
        # retrieved once and threaded into every brief. Feeds the refiner brief ONLY
        # -- never self.judge (maker != checker). Empty on a target's first run, or
        # when reuse is disabled for an ablation's reuse-OFF leg (U6), so behavior
        # degrades to today's loop.
        if run is not None and not self.disable_reuse:
            reused_learnings = self.store.prior_learnings(
                target=run.target, lane=run.lane, cross_target=self.reuse_cross_target
            )
        else:
            reused_learnings = []
        # Reuse instrumentation (U5): how many prior learnings this run injected.
        # Observation-only -- never read into convergence/acceptance.
        self.store.record_injected_count(run_id, len(reused_learnings))

        # Plateau-pivot state (U2): on a sole plateau, rotate to the next-lowest
        # dimension once (per pivot budget) before stopping. ``pivot_offset`` resets
        # the plateau window; ``active_exclude`` demotes the hammered dims;
        # ``targeted_since_pivot`` records the lead dims tried since the last pivot.
        pivots_used = 0
        pivot_offset = 0
        active_exclude: set[str] = set()
        targeted_since_pivot: list[str] = []

        # Reflective state (plan 2026-06-20 U2): ``reflection_ctx`` is the trace-driven
        # ASI handed to the NEXT brief -- None on the first iteration. ``prior_kept_fixtures``
        # accumulates the failing fixtures of KEPT verdicts so the persistent/new split is
        # computed over the kept lineage, never raw store rows (which also hold rejected
        # attempts). Always populated; refiners read it protocol-bound so this is additive.
        reflection_ctx: ReflectionContext | None = None
        prior_kept_fixtures: set[str] = set()

        while True:
            plateaued = self.store.is_plateaued(
                run_id,
                self.budget.plateau_patience,
                on_score=self.budget.target_score is not None,
                since_iteration=pivot_offset,
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
                # Pivot ONLY on a sole plateau with budget remaining -- a cap stop
                # (iteration/token/wall) always wins and never pivots.
                if decision.reason_code == cv.PLATEAU and pivots_used < self.budget.plateau_pivots:
                    pivots_used += 1
                    pivot_offset = n  # reset the plateau window to post-pivot iterations
                    active_exclude |= set(targeted_since_pivot)
                    targeted_since_pivot = []
                else:
                    return self._finish(run_id, decision, verdict, n)

            # --- REFACTORING ---
            token = self.checkpoint.snapshot()
            brief = build_refactor_brief(
                verdict,
                goal,
                recurring_failures=recurring_fixtures,
                exclude_dims=list(active_exclude) or None,
                upstream_outcomes=self.upstream_context,
                reflection=reflection_ctx,  # trace-driven ASI from the prior attempt (U2)
                reused_learnings=reused_learnings,  # cross-run reuse flywheel (plan 2026-06-21 U3)
            )
            if brief.target_dimensions:
                targeted_since_pivot.append(brief.target_dimensions[0])
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

            # Fork-Card decision channel (U6): resolve + record any decisions the
            # agent emitted this iteration; a grounded resolver overrule is a
            # reversal. Always recorded, even on the safety-halt path below.
            fork_reversal = self._process_fork_cards(run_id, n)

            # Safety failure introduced by the refactor: roll back, halt, no ship.
            # Safety is terminal and wins over a fork reversal.
            if not new_verdict.safety_ok:
                self.checkpoint.restore(token)
                return self._finish(
                    run_id,
                    cv.Decision(cv.BLOCKED_SAFETY, "refactor introduced a safety failure"),
                    new_verdict,
                    n,
                )

            # ``last_attempt`` / ``last_outcome`` feed the reflection handed to the
            # NEXT brief (plan 2026-06-20 U2). The safety-halt path above already
            # returned, so only the three keep/reverse/rollback branches reach here.
            last_attempt: str | None = diff_ref
            if fork_reversal:
                # The resolver overruled the agent's chosen default for a fork on
                # this iteration -> reverse via the existing rollback, even when
                # the grade improved (KTD2). Keep the prior verdict; do not compound.
                self.checkpoint.restore(token)
                last_outcome = "reversed"
            elif cv.is_improvement(verdict, new_verdict, self.budget):
                # Improvement accepted and kept -> compound (never on rollback).
                self.compounder.compound(
                    f"iteration {n}: grade {verdict.grade} -> {new_verdict.grade} "
                    f"by targeting {brief.target_dimensions[:2]}",
                    regression_test_ref=diff_ref,
                    grade_delta=float(grade_rank(new_verdict.grade) - grade_rank(verdict.grade)),
                )
                verdict = new_verdict
                accepted += 1
                last_outcome = "accepted"
                # Periodic System-2 compression pass (U7), on accepted-fix cadence.
                if self.compressor is not None and accepted % self.budget.compression_interval == 0:
                    result = self.compressor.run(run_id, tool_path)
                    verdict = result.after
                    n += 1
                    self._record(run_id, n, verdict, diff_ref="compression")
                    # The kept verdict now came from compression, not the refactor diff;
                    # don't tell the next refiner "your edit produced this" (U2).
                    last_attempt = None
            else:
                # Regression or no gain -> roll back; keep the prior verdict.
                self.checkpoint.restore(token)
                last_outcome = "rolled_back"

            # Assemble the reflection for the next iteration from the KEPT verdict
            # (judge-sourced only -- maker != checker, KTD3) and advance the kept
            # lineage so persistence is measured against prior kept states.
            reflection_ctx = self._build_reflection(verdict, last_attempt, last_outcome, prior_kept_fixtures)
            prior_kept_fixtures |= set(verdict.failing_fixtures)

    # ----- helpers --------------------------------------------------------

    @staticmethod
    def _build_reflection(
        kept: Verdict, attempted: str | None, outcome: str, prior_kept_fixtures: set[str]
    ) -> ReflectionContext:
        """Compose the trace-driven ASI for the next brief (plan 2026-06-20 U2).

        ``kept`` is the verdict that survived this iteration (judge-sourced only).
        ``persistent`` fixtures fail now AND failed in a prior kept verdict (they
        resisted edits); ``new`` fixtures are first-seen. Pure -- no I/O.
        """
        live = list(kept.failing_fixtures)
        persistent = [fx for fx in live if fx in prior_kept_fixtures]
        new = [fx for fx in live if fx not in prior_kept_fixtures]
        return ReflectionContext(
            prior_grade=kept.grade,
            prior_score=kept.score,
            prior_dims=dict(kept.dims),
            attempted=attempted,
            outcome=outcome,
            persistent_fixtures=persistent,
            new_fixtures=new,
            judge_feedback=getattr(kept, "feedback", "") or "",
        )

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

    def _process_fork_cards(self, run_id: int, n: int) -> bool:
        """Resolve, record, and collect the Fork-Cards the refiner emitted this
        iteration (U6). Returns ``True`` when a grounded resolution reverses the
        agent's default. Cards are read protocol-bound (``getattr``), so a refiner
        that emits none is a no-op. With no resolver wired, cards are recorded as
        ``recorded`` and surfaced for end-review but never reverse the build.
        """
        cards = getattr(self.refiner, "last_fork_cards", None) or []
        reversal = False
        for card in cards:
            resolution = self.resolver.resolve(card) if self.resolver is not None else None
            if resolution is not None:
                decision = resolution.decision
                chosen = resolution.chosen_option_id
                basis = resolution.basis
                if resolution.is_reversal:
                    reversal = True
            else:
                decision = "recorded"
                chosen = None
                basis = card.basis
            self.store.record_fork_card(
                run_id,
                card_id=card.id,
                options=[o.to_dict() for o in card.options],
                spec_clause=card.spec_clause,
                chosen_default=card.chosen_default,
                reversibility=card.reversibility,
                blast_radius=card.blast_radius,
                basis=basis,
                decision=decision,
                chosen_option=chosen,
                iteration_id=n,
            )
            self._collected_fork_cards.append(card)
        return reversal

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
        return LoopOutcome(
            final_state=state,
            grade=verdict.grade,
            reason=decision.reason,
            iterations=n,
            score=verdict.score,
            dims=dict(verdict.dims),
            fork_cards=list(getattr(self, "_collected_fork_cards", [])),
        )
