"""Target router (U3, R1) — now a thin shim over the domain registry (U11).

Classification lives in the ``DomainRegistry``: ``route`` delegates to it and
adapts the resolved software domain back into the legacy ``LaneDecision`` its
callers (CLI, autonomous runner) expect, so a new domain registers without
touching this file (R11) while existing behavior is byte-identical (R2).

  - service lane  -> CLI-Printing-Press: http(s) URL, .har file, or OpenAPI spec
  - codebase lane -> CLI-Anything: local directory or git repo URL

Ambiguous inputs resolve by precedence (local path > spec file > URL); a forced
``--lane`` always wins. The ``LaneDecision`` carries the reason so the
classification is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Lane
from .domains.registry import REGISTRY


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

    try:
        domain = REGISTRY.resolve(target)
    except ValueError:
        # Preserve the router's actionable, --lane-aware guidance (R2).
        raise ValueError(
            f"could not classify target {target!r}. "
            "Accepted: a local directory/repo, a .har file, an OpenAPI spec "
            "(.json/.yaml/.yml), a git repo URL, or an http(s) service URL. "
            "Use --lane to force a lane."
        ) from None

    # The legacy router only ever drives software domains; a non-software domain
    # (e.g. the sim domain) is resolved through the registry directly, not here.
    if not hasattr(domain, "lane") or not hasattr(domain, "factory_key"):
        raise ValueError(
            f"target {target!r} resolved to domain {domain.name!r}, which is not a "
            "lane-based software domain — resolve it via the domain registry, not route()."
        )
    return LaneDecision(domain.lane, domain.factory_key, target, domain.reason(target))
