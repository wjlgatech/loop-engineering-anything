"""Vague idea -> initial spec document (plan 2026-06-21 U8, the generate-analog).

Wraps the existing planning capability (`ce-brainstorm`/`ce-plan`/`lavish`) to turn a
free-text idea into a first-draft spec — it does NOT reinvent generation. The actual
generation is injectable (``generate``); the default scaffold lets the loop run
without quota, and the live generator is first-light-gated. The produced spec is the
artifact the rubric grader (U7) scores and the spec refiner (U8) improves.
"""

from __future__ import annotations

import os

from ..adapters.safety import run_tool

_SCAFFOLD = """# spec: {idea}

## Problem Frame
{idea}

## Requirements
- R1 — (define the first requirement)

## Implementation Units

### U1. (first unit)
Advances R1.

## Scope Boundaries
(define non-goals)
"""


_GEN_PROMPT = (
    "/ce-plan {idea}\n\nWrite a complete spec as Markdown to stdout: a Problem Frame, "
    "numbered Requirements (R1, R2, ...), Implementation Units (### U1. ...) each with "
    "Test scenarios, and a Scope Boundaries section. Output ONLY the spec Markdown."
)


def _claude_generate(idea: str, *, executable: str, timeout: float) -> str:
    """Live generator: shell to the planning capability and return its spec Markdown.
    First-light-gated by quota; falls back to the scaffold on any infra failure so the
    loop still has a (low-grade) starting spec to improve."""
    res = run_tool([executable, "-p", _GEN_PROMPT.format(idea=idea)], timeout=timeout)
    out = (getattr(res, "stdout", "") or "").strip() if res is not None else ""
    return out or _SCAFFOLD.format(idea=idea)


def synthesize_spec(
    idea: str,
    dest_dir: str,
    *,
    generate=None,
    live: bool = False,
    executable: str = "claude",
    timeout: float = 30 * 60,
) -> str:
    """Write an initial spec for ``idea`` to ``<dest_dir>/spec.md`` and return its
    path. ``generate(idea) -> str`` overrides everything (test stub / custom). With
    ``live=True`` the default generator shells to the planning capability (`ce-plan`);
    otherwise it emits a minimal, intentionally low-grade scaffold for the loop to
    improve. Live generation is first-light-gated; it degrades to the scaffold on
    infra failure."""
    os.makedirs(dest_dir, exist_ok=True)
    if generate is not None:
        text = generate(idea)
    elif live:
        text = _claude_generate(idea, executable=executable, timeout=timeout)
    else:
        text = _SCAFFOLD.format(idea=idea)
    path = os.path.join(dest_dir, "spec.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path
