"""Target router (U3, R1).

Classifies a target into a lane and selects the factory:
  - service lane  -> CLI-Printing-Press: http(s) URL, .har file, or OpenAPI spec
  - codebase lane -> CLI-Anything: local directory or git repo URL

Ambiguous inputs resolve by precedence (local path > spec file > URL); a forced
``--lane`` always wins. Returns a ``LaneDecision`` carrying the reason so the
classification is auditable.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .config import Lane

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


@dataclass(frozen=True)
class LaneDecision:
    lane: Lane
    factory: str  # "printing-press" | "cli-anything"
    normalized_target: str
    reason: str


def _factory_for(lane: Lane) -> str:
    return "printing-press" if lane is Lane.SERVICE else "cli-anything"


def route(target: str, forced_lane: Lane | None = None) -> LaneDecision:
    """Classify ``target`` into a lane.

    Raises ``ValueError`` for empty or unrecognized input.
    """
    if target is None or not str(target).strip():
        raise ValueError("target is empty")
    target = str(target).strip()

    if forced_lane is not None:
        return LaneDecision(
            forced_lane,
            _factory_for(forced_lane),
            target,
            reason=f"forced via --lane {forced_lane.value}",
        )

    # Precedence 1: an existing local path is a codebase target.
    if os.path.exists(target):
        if os.path.isdir(target):
            return LaneDecision(Lane.CODEBASE, "cli-anything", target, "local directory")
        lower = target.lower()
        if lower.endswith(_HAR_SUFFIX):
            return LaneDecision(Lane.SERVICE, "printing-press", target, "HAR capture file")
        if lower.endswith(_OPENAPI_SUFFIXES):
            return LaneDecision(Lane.SERVICE, "printing-press", target, "OpenAPI spec file")
        # An existing non-spec file is treated as a codebase entry point.
        return LaneDecision(Lane.CODEBASE, "cli-anything", target, "local file")

    # Precedence 2: spec-like path that does not exist yet (still a spec target).
    lower = target.lower()
    if lower.endswith(_HAR_SUFFIX):
        return LaneDecision(Lane.SERVICE, "printing-press", target, "HAR capture file")
    if lower.endswith(_OPENAPI_SUFFIXES):
        return LaneDecision(Lane.SERVICE, "printing-press", target, "OpenAPI spec file")

    # Precedence 3: URLs. A git-repo URL is a codebase; any other URL is a service.
    if _GIT_REPO_URL.match(target):
        return LaneDecision(Lane.CODEBASE, "cli-anything", target, "git repository URL")
    if _URL.match(target) or target.startswith("git@"):
        return LaneDecision(Lane.SERVICE, "printing-press", target, "service URL")

    raise ValueError(
        f"could not classify target {target!r}. "
        "Accepted: a local directory/repo, a .har file, an OpenAPI spec "
        "(.json/.yaml/.yml), a git repo URL, or an http(s) service URL. "
        "Use --lane to force a lane."
    )
