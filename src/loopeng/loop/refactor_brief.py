"""Translate a Verdict into a focused refactor brief (U6).

Targets the lowest-scoring dimensions plus their failing fixtures -- not the
whole report -- so the refinement engine works on what actually moves the grade.
"""

from __future__ import annotations

from ..adapters.base import ReflectionContext, RefactorBrief, Verdict


def build_refactor_brief(
    verdict: Verdict,
    goal: str = "",
    recurring_failures: list | None = None,
    exclude_dims: list | None = None,
    upstream_outcomes: list | None = None,
    reflection: ReflectionContext | None = None,
    reused_learnings: list | None = None,
) -> RefactorBrief:
    # Rank dimensions lowest-score-first; those are where the grade is bleeding.
    ranked = [name for name, _ in sorted(verdict.dims.items(), key=lambda kv: kv[1])]
    # Plateau pivot (U2): demote already-tried dimensions to the back so the brief
    # rotates to the next-lowest. Excluded dims are kept (not dropped) so the
    # refiner still sees them, just deprioritized.
    if exclude_dims:
        excluded = set(exclude_dims)
        ranked = [d for d in ranked if d not in excluded] + [d for d in ranked if d in excluded]
    objective = goal or (
        f"Raise the grade from {verdict.grade} by fixing the lowest-scoring "
        f"dimensions first."
    )

    live = list(verdict.failing_fixtures)
    # Cross-run history (U1): only re-prioritize fixtures that are BOTH historically
    # recurring AND failing now -- live signal is never demoted below stale history.
    # Recurring fixtures that are passing now ride along as advisory context only.
    recurring = list(recurring_failures or [])
    live_set = set(live)
    recurring_and_live = [fx for fx in recurring if fx in live_set]
    if recurring_and_live:
        rest = [fx for fx in live if fx not in set(recurring_and_live)]
        live = recurring_and_live + rest
    advisory = [fx for fx in recurring if fx not in live_set]

    return RefactorBrief(
        goal=objective,
        target_dimensions=ranked,
        failing_fixtures=live,
        recurring_failures=advisory,
        upstream_outcomes=list(upstream_outcomes or []),  # fleet routing (plan-006 U3)
        reflection=reflection,  # trace-driven ASI; None on first iteration (plan 2026-06-20 U2)
        reused_learnings=list(reused_learnings or []),  # cross-run reuse flywheel (plan 2026-06-21 U3)
    )
