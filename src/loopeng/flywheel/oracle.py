"""Downstream-outcome oracle for the spec stage (plan 2026-06-21 U9).

The spec flywheel's proof can't rest on the rubric score alone -- the refiner could
learn to please the rubric without producing genuinely better specs (circularity). The
criterion-INDEPENDENT check is whether a *higher-rubric spec* actually yields a *better
downstream tool-loop outcome* (a higher first-attempt tool grade), an outcome the
spec-refiner cannot directly optimize. This module is the pure measurement; wiring it
to live spec->tool runs is first-light-gated.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..memory.store import grade_rank


@dataclass(frozen=True)
class SpecOutcome:
    """One spec and the downstream tool-loop result it produced."""

    spec_score: float          # rubric score of the spec (U7)
    tool_first_grade: str      # first-attempt grade of the tool built FROM that spec


def downstream_oracle(outcomes: list[SpecOutcome]) -> dict:
    """Does a higher rubric score predict a better downstream tool first-attempt grade?

    Concordance over all comparable pairs: for every pair whose spec scores differ,
    count it ``concordant`` when the higher-spec-score member also has the
    higher-or-equal tool grade, ``discordant`` otherwise. ``supports`` is True when a
    strict majority are concordant. This is grade-independent of the rubric (the tool
    grade comes from CLI-Judge, not the spec grader), so it can't be gamed by pleasing
    the rubric. Returns counts + ``supports``; ``supports`` is False on too little data.
    """
    concordant = discordant = 0
    for i in range(len(outcomes)):
        for j in range(i + 1, len(outcomes)):
            a, b = outcomes[i], outcomes[j]
            if a.spec_score == b.spec_score:
                continue  # not a comparable pair on the spec axis
            hi, lo = (a, b) if a.spec_score > b.spec_score else (b, a)
            if grade_rank(hi.tool_first_grade) >= grade_rank(lo.tool_first_grade):
                concordant += 1
            else:
                discordant += 1
    total = concordant + discordant
    return {
        "concordant": concordant,
        "discordant": discordant,
        "comparable_pairs": total,
        "supports": total > 0 and concordant > discordant,
    }
