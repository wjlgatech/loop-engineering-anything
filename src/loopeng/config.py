"""Configuration: budgets, convergence policy, and dependency definitions.

Holds the knobs the loop controller (U6) and preflight (U1) read. Budgets are
the multi-signal convergence policy's hard limits (KTD6, R5); the dependency
table is what preflight (U1) detects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Lane(str, Enum):
    """Target lane selected by the router (U3, R1)."""

    SERVICE = "service"  # URL / HAR / OpenAPI -> Printing-Press
    CODEBASE = "codebase"  # local dir / repo -> CLI-Anything


@dataclass(frozen=True)
class Dependency:
    """An external tool the orchestrator drives (KTD1).

    ``detect`` names how preflight confirms availability:
      - ``"binary"``  -> the tool is a PATH executable (``command -v``)
      - ``"skill"``   -> the tool is a Claude Code skill/slash-command, not a
                         PATH binary; presence is confirmed differently.

    This split is the fix for the doc-review finding that ``command -v`` alone
    would false-negative on skill-distributed tools (CLI-Anything, compound-
    engineering). See ``preflight.py``.
    """

    key: str
    label: str
    detect: str  # "binary" | "skill"
    probes: tuple[str, ...] = ()  # candidate executable names for "binary"
    lanes: tuple[Lane, ...] = ()  # lanes that require this tool; () = always
    refinement_engine: bool = False  # required for the refactor loop (U6)


# The four dependencies (plan Prerequisites / U1). Exactly one of the two
# factories is required per lane; the judge and the refinement engine are
# always required once a loop runs.
DEPENDENCIES: tuple[Dependency, ...] = (
    Dependency(
        key="printing-press",
        label="CLI-Printing-Press (service/API lane)",
        detect="binary",
        probes=("printing-press", "cli-printing-press"),
        lanes=(Lane.SERVICE,),
    ),
    Dependency(
        key="cli-anything",
        label="CLI-Anything (codebase lane)",
        detect="binary",
        probes=("cli-anything", "cli-hub"),
        lanes=(Lane.CODEBASE,),
    ),
    Dependency(
        key="cli-judge",
        label="CLI-Judge (referee)",
        detect="binary",
        probes=("cli-judge",),
        lanes=(),  # always required
    ),
    Dependency(
        key="compound-engineering",
        label="compound-engineering plugin (/ce-work, /ce-compound)",
        detect="skill",
        probes=(),
        lanes=(),  # always required
        refinement_engine=True,
    ),
)


@dataclass(frozen=True)
class Budget:
    """Multi-signal convergence policy limits (R5, KTD6).

    The loop stops at the first limit reached. ``token_budget`` of ``None``
    means token accounting is best-effort only (the doc-review flagged the
    measurement source as unresolved -- iteration count is the hard guarantee;
    tokens are advisory until a real source is wired).
    """

    target_grade: str = "A"
    max_iterations: int = 10
    plateau_patience: int = 3  # stop after N iterations with no grade gain
    token_budget: int | None = None  # advisory until a measurement source exists
    compression_interval: int = 5  # run History Compression every N iterations (U7)


@dataclass
class Config:
    budget: Budget = field(default_factory=Budget)
    # Where required-credential env vars are read from (security finding S-1):
    # the runner reads creds from the environment only, never from this file.
    required_env: tuple[str, ...] = ()
