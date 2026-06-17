"""Fork-Card: a build decision the spec/northstar did not determine (plan 2026-06-17 U1).

A Fork-Card is the first-class, gradable record of a mid-build "which option?" fork.
In the headless regime the coding agent emits one (instead of stalling) whenever a
choice is not settled by the spec, picks the most reversible reasonable default, and
keeps building. The supervisor resolves the card; the rest of the supervised loop
(resolver, persistence, end-review) consumes it.

This module owns only the *type* and its serialization. Parsing from the agent's
output lives in the refiner (U4); resolution in the resolver (U3); persistence in the
store (U5). ``from_dict`` is deliberately defensive: a malformed card raises
``ForkCardParseError`` so the refiner can skip-and-count it, never crash (KTD1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REVERSIBILITY = ("reversible", "hard_to_reverse", "irreversible")
BLAST_RADIUS = ("local", "module", "cross_cutting")

# Sentinel ``basis`` for a card with no grounding behind its chosen option -- the
# card is spec-silent and the oracle could not ground it, so it is flagged for
# end-review (R5). A *resolved* card carries a list of citation references instead.
UNRESOLVED = "unresolved"


class ForkCardParseError(ValueError):
    """A dict could not be mapped to a ForkCard. Callers catch + count; a malformed
    card is skipped, never crashes the refiner (KTD1)."""


@dataclass(frozen=True)
class ForkOption:
    """One enumerated choice on a fork."""

    id: str
    label: str
    description: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "description": self.description}


@dataclass(frozen=True)
class ForkCard:
    """A typed record of a single undetermined build decision (R1).

    ``chosen_default`` is the option id the agent built on (the most reversible
    reasonable choice) or ``None``. ``basis`` is either a list of citation
    references (a grounded resolution) or the ``UNRESOLVED`` sentinel.
    """

    id: str
    options: list  # list[ForkOption]
    spec_clause: str
    chosen_default: str | None = None
    reversibility: str = "reversible"
    blast_radius: str = "local"
    basis: Any = UNRESOLVED
    regime: str = "headless"
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.reversibility not in REVERSIBILITY:
            raise ForkCardParseError(
                f"unknown reversibility {self.reversibility!r}; expected one of {REVERSIBILITY}"
            )
        if self.blast_radius not in BLAST_RADIUS:
            raise ForkCardParseError(
                f"unknown blast_radius {self.blast_radius!r}; expected one of {BLAST_RADIUS}"
            )
        if not all(isinstance(o, ForkOption) for o in self.options):
            raise ForkCardParseError("options must be ForkOption instances")
        if self.chosen_default is not None and self.chosen_default not in {o.id for o in self.options}:
            raise ForkCardParseError(
                f"chosen_default {self.chosen_default!r} is not one of the option ids"
            )

    @property
    def is_unresolved(self) -> bool:
        """True when the card carries no grounding (flagged for end-review)."""
        return self.basis == UNRESOLVED or not self.basis

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "options": [o.to_dict() for o in self.options],
            "spec_clause": self.spec_clause,
            "chosen_default": self.chosen_default,
            "reversibility": self.reversibility,
            "blast_radius": self.blast_radius,
            "basis": self.basis,
            "regime": self.regime,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ForkCard":
        """Map a plain dict (e.g. parsed from the agent's JSON output) to a ForkCard.

        Defensive by contract: any structural problem raises ``ForkCardParseError``
        (never a bare ``KeyError`` / ``TypeError``) so the refiner can skip a
        malformed card and keep the valid ones.
        """
        if not isinstance(d, dict):
            raise ForkCardParseError(f"fork card must be a dict, got {type(d).__name__}")
        try:
            raw_options = d["options"]
            if not isinstance(raw_options, list) or not raw_options:
                raise ForkCardParseError("fork card 'options' must be a non-empty list")
            options = []
            for o in raw_options:
                if not isinstance(o, dict):
                    raise ForkCardParseError("each option must be a dict")
                options.append(
                    ForkOption(
                        id=str(o["id"]),
                        label=str(o.get("label", o["id"])),
                        description=str(o.get("description", "")),
                    )
                )
            return cls(
                id=str(d["id"]),
                options=options,
                spec_clause=str(d.get("spec_clause", "")),
                chosen_default=(None if d.get("chosen_default") is None else str(d["chosen_default"])),
                reversibility=str(d.get("reversibility", "reversible")),
                blast_radius=str(d.get("blast_radius", "local")),
                basis=d.get("basis", UNRESOLVED),
                regime=str(d.get("regime", "headless")),
                created_at=str(d.get("created_at", "")),
            )
        except ForkCardParseError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ForkCardParseError(f"malformed fork card: {exc}") from exc
