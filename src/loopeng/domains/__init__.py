"""Domain SDK + registry (U9/U11).

A *domain* binds a target shape (a service, a codebase, later a control policy)
to the concrete adapters the loop drives it with. The controller stays
domain-agnostic and depends only on the protocols in ``adapters/base.py``; a
domain is the seam that says *which* Factory/Judge/safety binding to use for a
given target. See ``base.Domain``.
"""

from .base import Domain

__all__ = ["Domain"]
