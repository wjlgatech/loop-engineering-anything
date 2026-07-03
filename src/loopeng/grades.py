"""Grade ranking — a pure, effect-free leaf module (plan 2026-06-22 U2 / KTD6).

Extracted from ``memory/store.py`` so the pure-core modules (``loop/convergence.py``,
``flywheel/oracle.py``, …) can rank grades WITHOUT importing the sqlite-owning store
module. This makes the functional-core purity claim structurally true, not just
direct-import true. Imports nothing from loopeng (cycle-free leaf).
"""

from __future__ import annotations

# CLI-Judge grades A-F (no E in the standard scheme); E is mapped defensively in
# case a suite emits it.
GRADE_RANK = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0}


def grade_rank(grade: str) -> int:
    """Numeric rank for a letter grade; unknown grades rank lowest."""
    return GRADE_RANK.get((grade or "").strip().upper(), -1)
