"""Domain registry — resolve a target into a registered ``Domain`` (U11, R11).

Supersedes the router's hard-coded service/codebase branching: classification
is now "ask each registered domain if the target is theirs," so a new domain
arrives as a registration, never as an edit to ``router.py`` or the controller
(wrap-don't-fork). The registry owns *selection*; the domain owns *binding*.
"""

from __future__ import annotations

from .base import Domain


class DomainRegistry:
    def __init__(self) -> None:
        self._domains: list[Domain] = []

    def register(self, domain: Domain) -> None:
        if any(d.name == domain.name for d in self._domains):
            raise ValueError(f"domain {domain.name!r} is already registered")
        self._domains.append(domain)

    def names(self) -> list[str]:
        return [d.name for d in self._domains]

    def resolve(self, target: str, forced: str | None = None) -> Domain:
        """Resolve ``target`` to a registered domain.

        ``forced`` selects a domain by name, overriding classification. Raises
        ``ValueError`` (listing registered domains) when nothing matches.
        """
        if forced is not None:
            for d in self._domains:
                if d.name == forced:
                    return d
            raise ValueError(
                f"unknown domain {forced!r}; registered: {', '.join(self.names()) or '(none)'}"
            )
        for d in self._domains:
            if d.classify(target):
                return d
        raise ValueError(
            f"could not classify target {target!r} into any registered domain "
            f"({', '.join(self.names()) or 'none'})."
        )


def default_registry() -> DomainRegistry:
    """The registry the router shim and runner resolve against."""
    from .software import SOFTWARE_CODEBASE, SOFTWARE_SERVICE

    reg = DomainRegistry()
    reg.register(SOFTWARE_SERVICE)
    reg.register(SOFTWARE_CODEBASE)
    return reg


REGISTRY = default_registry()
