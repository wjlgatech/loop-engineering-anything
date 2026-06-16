"""Software domains — service + codebase (U11, R2/R11).

Re-homes the router's hard-coded lane heuristics as two registered ``Domain``s
with **identical** classification. The precedence (local path > spec file > URL)
lives in one shared, reason-carrying classifier so ``router.route`` and each
domain's ``classify`` cannot drift. The concrete Factory/Judge instances stay
injected at the runner boundary (existing wiring); a software domain names the
binding (``lane`` / ``factory_key``), it does not manufacture the adapters.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from ..adapters.base import Factory, Judge
from ..config import Lane

_OPENAPI_SUFFIXES = (".json", ".yaml", ".yml")
_HAR_SUFFIX = ".har"
# A URL that looks like a git repository -> codebase lane, not service.
_GIT_REPO_URL = re.compile(
    r"""^(?:https?://|git@)         # scheme
        (?:github\.com|gitlab\.com|bitbucket\.org|[^/\s]*\bgit\b[^/\s]*)
        [:/].+                       # owner/repo
    """,
    re.VERBOSE | re.IGNORECASE,
)
_URL = re.compile(r"^https?://", re.IGNORECASE)


def classify_software(target: str) -> tuple[Lane, str] | None:
    """Classify a software target by the existing precedence, carrying the reason.

    Returns ``(lane, reason)`` or ``None`` when the target is not a recognized
    software target (the registry turns ``None`` into an actionable error). This
    is the single source of truth both the router shim and the domain
    ``classify`` methods read, so they cannot diverge (R2).
    """
    t = str(target).strip()
    if not t:
        return None

    # Precedence 1: an existing local path is a codebase target.
    if os.path.exists(t):
        if os.path.isdir(t):
            return (Lane.CODEBASE, "local directory")
        lower = t.lower()
        if lower.endswith(_HAR_SUFFIX):
            return (Lane.SERVICE, "HAR capture file")
        if lower.endswith(_OPENAPI_SUFFIXES):
            return (Lane.SERVICE, "OpenAPI spec file")
        # An existing non-spec file is treated as a codebase entry point.
        return (Lane.CODEBASE, "local file")

    # Precedence 2: spec-like path that does not exist yet (still a spec target).
    lower = t.lower()
    if lower.endswith(_HAR_SUFFIX):
        return (Lane.SERVICE, "HAR capture file")
    if lower.endswith(_OPENAPI_SUFFIXES):
        return (Lane.SERVICE, "OpenAPI spec file")

    # Precedence 3: URLs. A git-repo URL is a codebase; any other URL is a service.
    if _GIT_REPO_URL.match(t):
        return (Lane.CODEBASE, "git repository URL")
    if _URL.match(t) or t.startswith("git@"):
        return (Lane.SERVICE, "service URL")

    return None


@dataclass(frozen=True)
class SoftwareDomain:
    """A software target shape (service or codebase) bound to its lane + factory.

    Satisfies the ``Domain`` protocol. ``factory()``/``judge()`` return ``None``
    here because the concrete generator is injected by ``factory_key`` and the
    CLI-Judge adapter path is target-specific — both are wired at the runner
    boundary, not owned by the domain (keeps the existing wiring, R2).
    """

    name: str
    lane: Lane
    factory_key: str  # "printing-press" | "cli-anything"
    dependencies: frozenset[str]

    def classify(self, target: str) -> bool:
        m = classify_software(target)
        return m is not None and m[0] is self.lane

    def reason(self, target: str) -> str:
        """Auditable classification reason for this target (router compatibility)."""
        m = classify_software(target)
        return m[1] if m else ""

    def factory(self) -> Factory | None:
        return None  # injected at the runner boundary via factory_key

    def judge(self) -> Judge | None:
        return None  # CLI-Judge bound per-target by the caller (adapter path varies)


SOFTWARE_SERVICE = SoftwareDomain(
    name="software-service",
    lane=Lane.SERVICE,
    factory_key="printing-press",
    dependencies=frozenset({"printing-press", "cli-judge", "compound-engineering"}),
)
SOFTWARE_CODEBASE = SoftwareDomain(
    name="software-codebase",
    lane=Lane.CODEBASE,
    factory_key="cli-anything",
    dependencies=frozenset({"cli-anything", "cli-judge", "compound-engineering"}),
)
