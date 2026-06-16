"""Referee integrity: the maker/checker contract + verification gates (U17, R6/R10).

This module is the *teeth* behind "a target can be anything" — it makes "maker ≠
checker" an enforced precondition rather than a convention, and it adds the
anti-cognitive-surrender gate the Loop-Engineering posts demand for unattended
loops ("'done' is a claim until confirmed").

Three contract assertions, all **fail-closed** before a loop runs (mirroring the
credential-gate fail-fast shape in ``autonomous/runner.py`` — names, not values):

  1. **maker ≠ checker** — the ``Refiner`` (maker) and the ``Judge`` (checker)
     must be distinct objects. Two function calls on the *same* agent is not a
     referee; it is the maker grading itself (R10).
  2. **referee immutability** — the referee definition is immutable *to the
     maker*. We model this at the contract level: the maker's declared write
     surface must not contain the referee's files. The filesystem-boundary
     enforcement that backs this for the sim domain lives later (KTD6); here the
     contract is domain-general (operate on declared paths, not a live cwd).
  3. **held-out disjointness** — the final grade is computed on held-out
     evaluation seeds the maker never saw. The dev seeds (the maker's reward
     signal) and the held-out seeds (the final grade) must not overlap (KTD6).

These are the System-2 checks (plan-001 R12): the maker is System-1 (fast,
hill-climbing on the reward); integrity is the slow, deliberate verification that
the reward was not gamed. A domain wiring that fails any of these is rejected
*before* any work starts, so a reward-hacked configuration can never run.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import VerificationGate


class IntegrityError(RuntimeError):
    """A maker/checker contract violation. Raised fail-closed, before a loop runs."""


def assert_maker_distinct_from_checker(refiner: object, judge: object) -> None:
    """Reject a wiring where the maker (``refiner``) and checker (``judge``) are
    the same object (R10). Identity, not type: two *different* objects that
    happen to share a class are still maker ≠ checker.

    Fail-closed with a name, never the object repr (a refiner may carry creds).
    """
    if refiner is None or judge is None:
        raise IntegrityError("maker/checker integrity: refiner and judge must both be wired")
    if refiner is judge:
        raise IntegrityError(
            "maker/checker integrity: the maker (refiner) and checker (judge) are the "
            "same object — a maker cannot referee its own work (R10)"
        )


def assert_referee_immutable_to_maker(
    referee_paths: Iterable[str], maker_write_paths: Iterable[str]
) -> None:
    """Reject a wiring where the maker's write surface can reach the referee
    definition (R6/KTD6).

    Domain-general contract: the maker declares the paths it may write
    (``maker_write_paths`` — e.g. a policy-only subdirectory); the referee
    declares the paths that define the grade (``referee_paths`` — the judge,
    reward, and held-out seed files). If any referee path is inside (or equal
    to) any maker write path, the maker could tamper with the referee, so the
    wiring is rejected. The filesystem boundary that *enforces* this at run time
    (scoping the Refiner's cwd) lives in a later unit; here we reject the
    mis-wiring at the contract level.
    """
    makers = [_norm(p) for p in maker_write_paths]
    for referee in referee_paths:
        r = _norm(referee)
        for maker in makers:
            if _is_within(r, maker):
                raise IntegrityError(
                    "referee-immutability: a referee path is inside the maker's write "
                    f"surface (referee={os.path.basename(r)!r} under "
                    f"maker={os.path.basename(maker)!r}) — the maker could tamper with "
                    "the referee (R6/KTD6)"
                )


def assert_heldout_disjoint(dev_seeds: Iterable[int], heldout_seeds: Iterable[int]) -> None:
    """Reject a final-grade wiring whose held-out seeds overlap the maker's dev
    seeds (R6/KTD6).

    The maker is trained/refined against ``dev_seeds`` (its reward signal); the
    final grade is computed over ``heldout_seeds`` the maker never saw. Any
    overlap means the maker could overfit to (game) seeds that also score the
    final grade. Also rejects an *empty* held-out set: a grade over no unseen
    seeds is not a held-out grade at all.
    """
    dev = set(dev_seeds)
    held = set(heldout_seeds)
    if not held:
        raise IntegrityError(
            "held-out disjointness: the held-out seed set is empty — the final grade "
            "must be computed over seeds the maker never saw (R6/KTD6)"
        )
    overlap = dev & held
    if overlap:
        raise IntegrityError(
            "held-out disjointness: dev seeds and held-out seeds overlap "
            f"({sorted(overlap)}) — the maker would be graded on seeds it trained on "
            "(R6/KTD6)"
        )


def assert_loop_integrity(
    *,
    refiner: object,
    judge: object,
    referee_paths: Iterable[str] = (),
    maker_write_paths: Iterable[str] = (),
    dev_seeds: Iterable[int] | None = None,
    heldout_seeds: Iterable[int] | None = None,
) -> None:
    """Run every applicable contract assertion (the single preflight call).

    ``maker ≠ checker`` is always checked. The immutability and held-out checks
    are only enforced when the domain declares the relevant inputs (a
    letter-grade software domain has no seeds; a sim domain does) — but when a
    domain declares *one* of a held-out pair, it must declare both, so a
    half-wired held-out grade cannot slip through.
    """
    assert_maker_distinct_from_checker(refiner, judge)

    if referee_paths or maker_write_paths:
        assert_referee_immutable_to_maker(referee_paths, maker_write_paths)

    declared_seeds = dev_seeds is not None or heldout_seeds is not None
    if declared_seeds:
        if dev_seeds is None or heldout_seeds is None:
            raise IntegrityError(
                "held-out disjointness: a domain that declares seeds must declare both "
                "dev_seeds and heldout_seeds (R6/KTD6)"
            )
        assert_heldout_disjoint(dev_seeds, heldout_seeds)


def gate_requires_confirmation(
    gate: VerificationGate,
    *,
    scheduled: bool,
    env: dict[str, str] | None = None,
) -> bool:
    """Decide whether a ``CONVERGED`` outcome still needs human confirmation
    before it may be treated as shippable (R10).

    The access-control logic, in one place:

      - Gate OFF (``require_human_confirm=False``) → never required.
      - ``scheduled`` (unattended) run → **always required**, regardless of the
        CI flag. A scheduler setting ``CI=true`` in its own environment cannot
        silently auto-ship a reward-hacked result (anti-surrender default).
      - Attended run with the CI-infrastructure var truthy → bypassed (CI owns
        that var; a CLI caller does not control it).
      - Otherwise → required.

    Returns ``True`` when confirmation is still owed (i.e. NOT yet shippable).
    """
    if not gate.require_human_confirm:
        return False
    if scheduled:
        return True
    env = os.environ if env is None else env
    if _truthy(env.get(gate.ci_env_var)):
        return False
    return True


def confirm_convergence(
    gate: VerificationGate,
    *,
    scheduled: bool,
    confirmed: bool = False,
    env: dict[str, str] | None = None,
) -> bool:
    """Return whether a ``CONVERGED`` outcome is **shippable** now.

    ``confirmed`` is the human's affirmative ("yes, this is really done"). It is
    only honoured when confirmation is actually required; when the gate does not
    require confirmation (gate off, or attended CI bypass) the result is
    shippable without it. A scheduled run is shippable only with an explicit
    ``confirmed=True`` — a scheduler cannot fabricate the bypass via ``CI``.
    """
    if not gate_requires_confirmation(gate, scheduled=scheduled, env=env):
        return True
    return bool(confirmed)


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def _norm(path: str) -> str:
    return os.path.normpath(os.path.abspath(path))


def _is_within(inner: str, outer: str) -> bool:
    """True if normalized ``inner`` is ``outer`` or lives under it."""
    if inner == outer:
        return True
    return inner.startswith(outer + os.sep)
