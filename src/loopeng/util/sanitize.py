"""Shared text sanitizer for any operator-/model-/cross-run-sourced text that is
later rendered into an LLM prompt (plan 2026-06-21 R4).

Strips control characters + shell metacharacters and bounds length so the text is
safe to interpolate into either refiner's prompt with no per-path asymmetry, and —
critically for the learning-reuse flywheel — so it is sanitized *at the write path*
(``record_learning``) and can never persist unsanitized, crossing runs or targets.
Extracted from ``adapters/judge.py`` so ``memory/store.py`` and ``adapters/judge.py``
share one implementation without a circular import.
"""

from __future__ import annotations

DEFAULT_MAX = 600  # bound the text -- a dimension-level summary, not a transcript
_SHELL_METACHARS = frozenset("`$;|&><\\\"'")


def sanitize_text(text: str, *, max_len: int = DEFAULT_MAX) -> str:
    """Strip control chars + shell metacharacters and truncate to ``max_len``."""
    cleaned = "".join(
        ch for ch in str(text)
        if (ch == " " or ch.isprintable()) and ch not in _SHELL_METACHARS
    )
    return cleaned[:max_len].strip()
