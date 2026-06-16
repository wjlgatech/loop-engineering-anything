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
    # Continuous score target for domains whose referee emits a score, not a
    # letter (a stochastic sim referee, R3). When set, convergence and
    # acceptance decide on the score (after the unbypassable safety gate, and
    # in place of the letter ladder); when None, the letter path is unchanged.
    target_score: float | None = None
    max_iterations: int = 10
    plateau_patience: int = 3  # stop after N iterations with no grade gain
    # Token budget, enforced ONLY for refiners that report cost (U4). The
    # controller threads each refactor's ``last_token_cost`` into a running total
    # and stops the loop once it crosses this budget. A refiner that reports no
    # cost (``last_token_cost is None``) cannot advance this gate -- the loop logs
    # a one-time warning if a token_budget is set against such a refiner and
    # relies on ``max_wall_seconds`` as the universal backstop. ``None`` disables
    # the token gate entirely.
    token_budget: int | None = None
    # Wall-clock budget in seconds (U4) -- the universal cost backstop, parallel
    # to ``max_iterations``. Enforced for every refiner regardless of whether it
    # reports token cost. ``None`` disables it.
    max_wall_seconds: float | None = None
    compression_interval: int = 5  # run History Compression every N accepted fixes (U7)
    # Noise band for grade stability (P0 #2). A same-letter iteration only counts
    # as an improvement when the continuous score rises by more than this margin,
    # so sub-noise jitter from a non-deterministic judge is not mistaken for gain.
    # Set from a `probe_grade_variance` measurement; 0.0 = letter-grade only.
    min_score_gain: float = 0.0


@dataclass(frozen=True)
class VerificationGate:
    """Anti-cognitive-surrender human-confirm gate (U17, R10).

    A ``CONVERGED`` outcome is a *claim*, not a shipped fact ("'done' is a claim
    until confirmed"). When this gate is on, a converged result is not marked
    shippable until a human confirms it — defeating a reward-hacked maker that
    declares victory.

    **Bypass is access-controlled (security finding).** The gate is ON by
    default. There is deliberately **no caller-settable bypass flag**: a CLI
    caller (or a scheduler authoring its own invocation) must not be able to
    silently auto-ship. The only bypass keys on a *CI-infrastructure* env var
    (``ci_env_var``, default ``CI``) that the build platform owns, NOT the
    caller. And ``scheduled`` (unattended) runs default to confirm-required
    **regardless of the CI flag** — so a scheduler cannot disable the gate by
    setting ``CI=true`` in its own environment (anti-surrender default, R10).
    """

    require_human_confirm: bool = True  # gate ON by default
    ci_env_var: str = "CI"  # the CI-infrastructure var that may bypass (attended only)


@dataclass
class Config:
    budget: Budget = field(default_factory=Budget)
    # Where required-credential env vars are read from (security finding S-1):
    # the runner reads creds from the environment only, never from this file.
    required_env: tuple[str, ...] = ()
    gate: VerificationGate = field(default_factory=VerificationGate)
