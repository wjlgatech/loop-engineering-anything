"""The ``Domain`` plugin contract (U9, R1/R11).

A domain is the generalization seam: it classifies a target and binds the
concrete adapters the (unchanged) controller drives. Generalizing here — rather
than adding branches to ``loop/controller.py`` — is how "a target can be
anything" is expressed without new controller states (KTD1).

This module imports only the adapter protocols, never the controller, so the
dependency arrow stays controller → protocols ← domain (the controller never
learns a domain exists).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..adapters.base import Factory, Judge


@runtime_checkable
class Domain(Protocol):
    """Binds a target shape to its loop adapters.

    A domain answers three things: *is this target mine?* (``classify``), *how
    is its v0 artifact produced?* (``factory`` — ``None`` for a refine-only
    adopt-as-baseline domain, KTD5), and *who referees it?* (``judge``). The
    cross-domain safety signal travels on ``Verdict.safety_ok`` (the judge owns
    its per-domain safety derivation, KTD2), so it is not a separate accessor
    here. ``dependencies`` names the external tools the domain needs, for
    preflight gating.
    """

    @property
    def name(self) -> str:
        """Stable identifier, e.g. ``"software-service"`` / ``"physical-ai-sim"``."""
        ...

    @property
    def dependencies(self) -> frozenset[str]:
        """External tool/extra names this domain requires (preflight gate)."""
        ...

    def classify(self, target: str) -> bool:
        """True if this domain owns ``target`` (used by the U11 registry)."""
        ...

    def factory(self) -> Factory | None:
        """The generator for the v0 artifact, or ``None`` for a refine-only
        (adopt-as-baseline) domain that ingests an existing artifact (KTD5)."""
        ...

    def judge(self) -> Judge:
        """The referee that produces a ``Verdict`` for this domain."""
        ...
