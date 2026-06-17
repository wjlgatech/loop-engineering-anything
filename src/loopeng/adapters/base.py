"""Internal contracts and protocols (KTD2).

These normalize the four tools' surfaces into a small set of types the loop
controller depends on, so the controller never touches a real CLI directly and
is fully testable against fakes/recorded verdicts. The concrete bindings to the
real tools (U4/U5) implement these protocols.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Verdict:
    """A referee result, normalized across domains (U5/U9, R2/R3).

    ``score`` is the **primary continuous signal** every domain projects onto;
    ``grade`` is a coarse letter every domain also projects (software uses
    CLI-Judge's native letter, a sim domain bands mean reward), kept non-null so
    the controller / ``LoopOutcome`` / NOT-NULL schema stay untouched (KTD1).
    ``dims`` is a free-form per-dimension dict. ``safety_ok`` is the single
    cross-domain safety signal: ``False`` whenever a safety dimension failed OR
    the gate capped the grade; the controller treats it as terminal (KTD5, R3).
    """

    grade: str
    score: float
    dims: dict  # per-dimension scores, e.g. {"correctness": 30, "safety": 20, ...}
    safety_ok: bool
    failing_fixtures: list = field(default_factory=list)


@dataclass(frozen=True)
class GenerateResult:
    """A factory's output, normalized (U4, R1)."""

    tool_path: str
    lane: str
    ok: bool
    manifest: dict = field(default_factory=dict)
    logs: str = ""


@runtime_checkable
class Factory(Protocol):
    """Generates an agent-native CLI from a target (CLI-Printing-Press / CLI-Anything)."""

    def generate(self, target: str, goal: str) -> GenerateResult: ...


@runtime_checkable
class Judge(Protocol):
    """Grades a generated tool against reality (CLI-Judge)."""

    def judge(self, tool_path: str) -> Verdict: ...


@dataclass(frozen=True)
class RefactorBrief:
    """Instruction handed to the refinement engine (built from a Verdict)."""

    goal: str
    target_dimensions: list  # lowest-scoring dimensions, ranked
    failing_fixtures: list
    # Fixtures that recur across prior runs of this target but are NOT failing in
    # the current verdict -- advisory context only, never ahead of live failures
    # (plan-005 U1). Fixtures that recur AND fail now are promoted within ``failing_fixtures``.
    recurring_failures: list = field(default_factory=list)
    # Outcomes of upstream fleet items this item depends on -- caller-injected
    # advisory context (plan-006 U3). Distinct from ``recurring_failures``: that is
    # store-derived fixture strings; this is structured cross-item outcome dicts
    # routed by the fleet coordinator. Empty for a non-fleet (single-target) run.
    upstream_outcomes: list = field(default_factory=list)


@runtime_checkable
class Refiner(Protocol):
    """Applies a refactor to the tool (compound-engineering /ce-work).

    Returns a diff reference (path/sha) for the applied change, or ``None`` if
    nothing was applied. The brief content is passed as structured data; the
    refiner must never interpolate it into a shell command (security finding).

    ``last_token_cost`` is the optional per-refactor token cost the controller
    threads into the budget gate (U4). It is ``None`` when the refiner cannot
    report cost (e.g. a free-tier LLM); the controller then falls back to the
    wall-clock budget.

    ``last_infra_failure`` is ``True`` when the last ``refactor`` failed for
    *infrastructure* reasons (timeout / non-zero exit / a fully-throttled
    provider chain) rather than producing a clean no-change (U3). The controller
    reads it to retry transient failures; a refiner that omits it would silently
    forgo retries, so it is part of the contract.

    ``last_fork_cards`` is the list of Fork-Cards the agent emitted on the last
    refactor (plan 2026-06-17 U4) -- build decisions the spec did not determine.
    Empty when the refiner emits none or cannot report them; the controller reads
    it protocol-bound (via ``getattr``) so a refiner that omits it is harmless.

    All are declared on the protocol so the controller reads them protocol-bound
    rather than reaching into a concrete refiner class.
    """

    last_token_cost: int | None
    last_infra_failure: bool
    last_fork_cards: list

    def refactor(self, tool_path: str, brief: RefactorBrief) -> str | None: ...


@dataclass(frozen=True)
class OracleVerdict:
    """An oracle's answer to one Fork-Card (plan 2026-06-17 U2).

    ``chosen_option_id`` is the option the oracle would pick; ``citations`` are the
    grounding references behind it (a Vision-Kernel clause, a person-map node). A
    verdict is **grounded** only when it names an option AND carries at least one
    citation -- a closed-set scorer with no grounding returns an empty verdict and
    the resolver escalates (anti preference-hallucination, origin idea #2).
    """

    chosen_option_id: str | None = None
    citations: list = field(default_factory=list)

    @property
    def grounded(self) -> bool:
        return self.chosen_option_id is not None and bool(self.citations)


@runtime_checkable
class Oracle(Protocol):
    """Answers a Fork-Card from the user's persona/digital-twin.

    The oracle that ANSWERS a fork must never be the ``Judge`` that GRADES the
    build (oracle ≠ checker, enforced in ``loop.integrity``) -- otherwise persona
    preference launders into "quality". ``fork_card`` is left untyped here to keep
    the adapters layer free of a ``loop`` import; concrete oracles accept a
    ``loop.fork_card.ForkCard``.
    """

    def resolve(self, fork_card) -> "OracleVerdict": ...


@runtime_checkable
class Compounder(Protocol):
    """Records a learning + regression test on an accepted fix (/ce-compound)."""

    def compound(self, summary: str, *, regression_test_ref: str | None = None) -> None: ...


@runtime_checkable
class Checkpoint(Protocol):
    """Snapshot/restore of the tool's state for regression rollback (U6).

    Backed by per-iteration git checkpoints in the real runner; the controller
    depends only on this protocol so rollback is testable in isolation.
    """

    def snapshot(self) -> str: ...

    def restore(self, token: str) -> None: ...
