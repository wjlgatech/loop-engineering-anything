"""Vague idea -> initial spec document (plan 2026-06-21 U8, the generate-analog).

Wraps the existing planning capability (`ce-brainstorm`/`ce-plan`/`lavish`) to turn a
free-text idea into a first-draft spec — it does NOT reinvent generation. The actual
generation is injectable (``generate``); the default scaffold lets the loop run
without quota, and the live generator is first-light-gated. The produced spec is the
artifact the rubric grader (U7) scores and the spec refiner (U8) improves.
"""

from __future__ import annotations

import os

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


def synthesize_spec(idea: str, dest_dir: str, *, generate=None) -> str:
    """Write an initial spec for ``idea`` to ``<dest_dir>/spec.md`` and return its
    path. ``generate(idea) -> str`` overrides the scaffold (e.g. the live ce-plan
    capability, or a test stub); the default emits a minimal, intentionally
    low-grade scaffold for the loop to improve."""
    os.makedirs(dest_dir, exist_ok=True)
    text = generate(idea) if generate is not None else _SCAFFOLD.format(idea=idea)
    path = os.path.join(dest_dir, "spec.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path
