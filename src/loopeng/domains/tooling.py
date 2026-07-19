"""Tooling domain — grade generated agentic tooling (U3, R11).

The generalization seam for the ecosystem-hub factory's *tooling* half: a target
that is a **skill** (a directory containing a ``SKILL.md``, or a path to one) is
owned by this domain and refereed by the deterministic ``ToolingJudge``.

``factory()`` is ``None`` — this is a **refine/grade-only** domain today (the
skill/plugin generator keyed off the KG is U4); the judge already lets the loop
grade an *existing* skill and drive a refiner toward Grade A, exactly as the
software-codebase refine-only path does. Unlike the software domains, this domain
returns a **real** ``judge()`` because the referee is self-contained (no
per-target adapter path to bind at the runner boundary).

Registered **before** the software domains so a ``SKILL.md``-bearing directory
routes here rather than being swept up by ``software-codebase`` (which claims any
existing directory). The classifier is strictly more specific — it requires an
actual ``SKILL.md`` — so a plain repo/dir/URL still falls through to software.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..adapters.base import Factory, Judge
from ..adapters.tooling_judge import ToolingJudge


def is_tooling_target(target: str) -> bool:
    """True if ``target`` is a skill: a ``SKILL.md`` file or a dir containing one."""
    t = str(target).strip()
    if not t:
        return False
    if os.path.isfile(t) and os.path.basename(t) == "SKILL.md":
        return True
    return os.path.isdir(t) and os.path.isfile(os.path.join(t, "SKILL.md"))


@dataclass(frozen=True)
class ToolingDomain:
    """A skill-shaped tooling artifact bound to the deterministic tooling referee."""

    name: str = "tooling-skill"
    dependencies: frozenset[str] = frozenset()  # deterministic; no external tool

    def classify(self, target: str) -> bool:
        return is_tooling_target(target)

    def factory(self) -> Factory | None:
        return None  # refine/grade-only until the KG-keyed skill Factory (U4)

    def judge(self) -> Judge:
        return ToolingJudge()


TOOLING_SKILL = ToolingDomain()
