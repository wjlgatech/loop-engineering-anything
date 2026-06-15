"""Dependency preflight (U1).

Detects whether the four external tools are available before a run starts, so
the loop fails fast with an actionable message rather than mid-run.

Detection is per-tool by mechanism (doc-review finding F-5): PATH binaries are
probed with ``shutil.which``; the compound-engineering plugin is a Claude Code
skill, not a PATH binary, so probing it as a binary would false-negative on a
correctly-installed environment. Skill detection is best-effort over known
plugin locations with an explicit env override for environments where it
cannot be confirmed automatically.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import DEPENDENCIES, Dependency, Lane


@dataclass(frozen=True)
class ToolStatus:
    key: str
    label: str
    available: bool
    detail: str  # how it was found, or why it wasn't


def _detect_binary(dep: Dependency) -> ToolStatus:
    for probe in dep.probes:
        found = shutil.which(probe)
        if found:
            return ToolStatus(dep.key, dep.label, True, f"found on PATH: {found}")
    probes = ", ".join(dep.probes) or "(none)"
    return ToolStatus(dep.key, dep.label, False, f"not on PATH (looked for: {probes})")


def _compound_engineering_locations() -> list[Path]:
    """Known on-disk locations for the compound-engineering Claude Code plugin."""
    home = Path(os.path.expanduser("~"))
    base = home / ".claude" / "plugins"
    return [
        base / "marketplaces" / "compound-engineering-plugin",
        base / "cache" / "compound-engineering-plugin",
    ]


def _detect_skill(dep: Dependency) -> ToolStatus:
    # Explicit override: trust the operator when auto-detection cannot confirm
    # a skill (e.g. a non-standard plugin path or a headless runner).
    env_key = f"LOOPENG_ASSUME_{dep.key.replace('-', '_').upper()}"
    if os.environ.get(env_key) == "1":
        return ToolStatus(dep.key, dep.label, True, f"assumed present via {env_key}=1")

    if dep.key == "compound-engineering":
        for loc in _compound_engineering_locations():
            if loc.exists():
                return ToolStatus(dep.key, dep.label, True, f"plugin found: {loc}")
        return ToolStatus(
            dep.key,
            dep.label,
            False,
            "compound-engineering plugin not found under ~/.claude/plugins "
            f"(override with LOOPENG_ASSUME_COMPOUND_ENGINEERING=1)",
        )

    return ToolStatus(dep.key, dep.label, False, "no skill detector registered")


def detect(dep: Dependency) -> ToolStatus:
    if dep.detect == "binary":
        return _detect_binary(dep)
    if dep.detect == "skill":
        return _detect_skill(dep)
    raise ValueError(f"unknown detect mechanism: {dep.detect!r}")


def preflight() -> list[ToolStatus]:
    """Detect every dependency. Order matches ``config.DEPENDENCIES``."""
    return [detect(dep) for dep in DEPENDENCIES]


def required_keys(lane: Lane) -> set[str]:
    """Keys of the tools required for a run on ``lane``.

    A tool is required when it declares no lanes (always required) or lists
    this lane. The other lane's factory is not required.
    """
    keys: set[str] = set()
    for dep in DEPENDENCIES:
        if not dep.lanes or lane in dep.lanes:
            keys.add(dep.key)
    return keys


def missing_for_lane(lane: Lane, statuses: list[ToolStatus] | None = None) -> list[ToolStatus]:
    """Return the unavailable tools that block a run on ``lane``."""
    statuses = statuses if statuses is not None else preflight()
    required = required_keys(lane)
    return [s for s in statuses if s.key in required and not s.available]
