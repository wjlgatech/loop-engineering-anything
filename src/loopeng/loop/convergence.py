"""Multi-signal convergence policy (U6, R5, KTD6).

Pure decision function: given the latest verdict and run state, decide whether
the loop continues or stops, and why. Multi-signal by design so the loop cannot
oscillate or degrade indefinitely (the "flying turd" guard):

  safety failure  -> blocked_safety (terminal, unbypassable; KTD5/R3)
  score >= target -> converged   [when budget.target_score is set; else letter path]
  grade >= target -> converged
  iteration cap   -> stopped (budget: max iterations)
  token cap       -> stopped (budget: token)   [only when a token budget is set]
  wall-clock cap  -> stopped (budget: wall)    [only when a wall budget is set]
  plateau         -> stopped (plateau)
  otherwise       -> continue

Time is passed in (``elapsed_seconds``) rather than read here, so ``evaluate``
stays a pure, side-effect-free decision function (the controller owns the clock).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..adapters.base import Verdict
from ..config import Budget
from ..memory.store import grade_rank

CONTINUE = "continue"
CONVERGED = "converged"
BLOCKED_SAFETY = "blocked_safety"
STOPPED = "stopped"


@dataclass(frozen=True)
class Decision:
    kind: str  # one of CONTINUE / CONVERGED / BLOCKED_SAFETY / STOPPED
    reason: str


def evaluate(
    verdict: Verdict,
    budget: Budget,
    *,
    iterations_done: int,
    plateaued: bool,
    tokens_spent: int = 0,
    elapsed_seconds: float = 0.0,
) -> Decision:
    # Safety is the first and unbypassable check (KTD5, R3). The score/letter
    # convergence predicates are reached ONLY past this gate (R6 — a high score
    # can never bypass a safety failure).
    if not verdict.safety_ok:
        return Decision(BLOCKED_SAFETY, "safety gate failed (grade capped); not shippable")

    # Convergence predicate: a continuous score target takes precedence when set
    # (the letter ladder is skipped entirely); otherwise the letter path is
    # unchanged (R2/R3, structural ordering per KTD4).
    if budget.target_score is not None:
        if verdict.score >= budget.target_score:
            return Decision(CONVERGED, f"reached target score {budget.target_score}")
    elif grade_rank(verdict.grade) >= grade_rank(budget.target_grade):
        return Decision(CONVERGED, f"reached target grade {budget.target_grade}")

    if iterations_done >= budget.max_iterations:
        return Decision(STOPPED, f"budget: max iterations ({budget.max_iterations}) reached")

    if budget.token_budget is not None and tokens_spent >= budget.token_budget:
        return Decision(STOPPED, f"budget: token budget ({budget.token_budget}) exhausted")

    if budget.max_wall_seconds is not None and elapsed_seconds >= budget.max_wall_seconds:
        return Decision(STOPPED, f"budget: wall-clock ({budget.max_wall_seconds}s) exceeded")

    if plateaued:
        return Decision(STOPPED, f"plateau: no gain over {budget.plateau_patience} iterations")

    return Decision(CONTINUE, "below target with budget remaining")


def is_improvement(old: Verdict, new: Verdict, budget: Budget) -> bool:
    """Whether ``new`` is a real improvement over ``old`` (P0 #2, noise-aware).

    Under a **score target** the decision is purely on the score delta vs the
    noise band -- so a real score gain or regression *inside one letter band* is
    not masked by the coarse letter (R3, KTD4 doc-review finding).

    Under the **letter ladder** (no score target): a strictly better letter
    grade always counts; a same-letter result counts only when the score rises
    by more than ``budget.min_score_gain`` (the noise band that keeps a jittery
    judge from registering phantom gains); a worse letter grade never counts.
    """
    if budget.target_score is not None:
        return (new.score - old.score) > budget.min_score_gain
    old_r, new_r = grade_rank(old.grade), grade_rank(new.grade)
    if new_r > old_r:
        return True
    if new_r < old_r:
        return False
    return (new.score - old.score) > budget.min_score_gain
