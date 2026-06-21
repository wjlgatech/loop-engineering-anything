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

import re

DEFAULT_MAX = 600  # bound the text -- a dimension-level summary, not a transcript
_SHELL_METACHARS = frozenset("`$;|&><\\\"'")


def sanitize_text(text: str, *, max_len: int = DEFAULT_MAX) -> str:
    """Strip control chars + shell metacharacters and truncate to ``max_len``."""
    cleaned = "".join(
        ch for ch in str(text)
        if (ch == " " or ch.isprintable()) and ch not in _SHELL_METACHARS
    )
    return cleaned[:max_len].strip()


# Target-specific token shapes redacted before a learning crosses a target boundary
# (flywheel U4 data-minimization): URLs, file-ish paths, and long hex/uuid identifiers.
# Distinct from sanitize_text's metachar scrub -- this minimizes cross-boundary leakage
# (one target's specifics/secrets) rather than neutralizing prompt structure.
_URL_RE = re.compile(r"https?://\S+")
_PATH_RE = re.compile(r"(?:[\w.\-]+)?/[\w./\-]+")
# Bare source filenames (precise extension allowlist -> avoids redacting prose like
# "e.g." or "N+1"); catches "api.go" that _PATH_RE misses for lacking a slash.
_FILE_RE = re.compile(
    r"\b[\w\-]+\.(?:go|py|ts|tsx|js|jsx|rb|java|rs|sql|json|ya?ml|sh|md|txt|c|cc|cpp|h|hpp|toml|cfg|ini)\b"
)
_LONGID_RE = re.compile(r"\b[0-9a-fA-F]{12,}\b")
_REDACTION = "<redacted>"


def redact_specifics(text: str) -> str:
    """Replace target-specific tokens (URLs, paths, source filenames, long
    identifiers) with a placeholder, so a learning reused ACROSS targets carries
    only the transferable lesson, not another target's URLs/paths/secrets
    (flywheel U4 / R7)."""
    out = _URL_RE.sub(_REDACTION, str(text))
    out = _PATH_RE.sub(_REDACTION, out)
    out = _FILE_RE.sub(_REDACTION, out)
    out = _LONGID_RE.sub(_REDACTION, out)
    return out
