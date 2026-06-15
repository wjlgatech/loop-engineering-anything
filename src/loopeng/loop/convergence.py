"""Multi-signal convergence policy (U6, R5, KTD6).

Pure decision function: given the latest verdict and run state, decide whether
the loop continues or stops, and why. Multi-signal by design so the loop cannot
oscillate or degrade indefinitely (the "flying turd" guard):

  safety failure  -> blocked_safety (terminal, unbypassable; KTD5/R3)
  grade >= target -> converged
  iteration cap   -> stopped (budget: max iterations)
  token cap       -> stopped (budget: token)   [only when a token budget is set]
  plateau         -> stopped (plateau)
  otherwise       -> continue
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
) -> Decision:
    # Safety is the first and unbypassable check (KTD5, R3).
    if not verdict.safety_ok:
        return Decision(BLOCKED_SAFETY, "safety gate failed (grade capped); not shippable")

    if grade_rank(verdict.grade) >= grade_rank(budget.target_grade):
        return Decision(CONVERGED, f"reached target grade {budget.target_grade}")

    if iterations_done >= budget.max_iterations:
        return Decision(STOPPED, f"budget: max iterations ({budget.max_iterations}) reached")

    if budget.token_budget is not None and tokens_spent >= budget.token_budget:
        return Decision(STOPPED, f"budget: token budget ({budget.token_budget}) exhausted")

    if plateaued:
        return Decision(STOPPED, f"plateau: no gain over {budget.plateau_patience} iterations")

    return Decision(CONTINUE, "below target with budget remaining")
