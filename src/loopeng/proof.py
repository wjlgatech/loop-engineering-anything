"""Proof pack: the rigorous before/after evidence for a verified loop (U3, R3).

A proof pack is what makes "catalog-v0 -> loop-converged" a *proof* rather than a
letter grade. It is assembled purely from a real run in the memory store +
``autonomous.report.build_report`` -- never hand-authored (R4/KTD2). It carries:

  - before / after grade and a per-dimension score diff,
  - iteration count and convergence terminal state,
  - wall-clock elapsed (from ``runs.started``/``runs.finished``),
  - token cost (best-effort; omitted, never faked, when no source is available),
  - the regression tests ``/ce-compound`` recorded on accepted fixes.

``StoreBackedCompounder`` is the wiring that makes the ``regression_tests`` field
real: the controller calls ``compounder.compound(...)`` on each accepted fix, but
neither built-in compounder writes to the store, so a refine run's ``learnings``
table would otherwise be empty. This wrapper records the learning to the store
*and* delegates to an inner compounder (e.g. the real ``/ce-compound`` binding).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .adapters.base import Compounder
from .memory.store import MemoryStore, grade_rank


class StoreBackedCompounder:
    """Records each accepted-fix learning to the store, then delegates.

    Wrap the real ``ClaudeCodeCompounder`` (or any ``Compounder``) so the proof
    pack's ``regression_tests`` field is populated for normal refine runs. The
    controller passes ``regression_test_ref`` (the applied diff ref) through; we
    persist it via ``store.record_learning``.
    """

    def __init__(self, store: MemoryStore, run_id: int, inner: Compounder | None = None):
        self.store = store
        self.run_id = run_id
        self.inner = inner

    def compound(self, summary: str, *, regression_test_ref: str | None = None) -> None:
        self.store.record_learning(self.run_id, None, summary, regression_test_ref)
        if self.inner is not None:
            self.inner.compound(summary, regression_test_ref=regression_test_ref)


def _elapsed_seconds(started: str | None, finished: str | None) -> float | None:
    if not started or not finished:
        return None
    try:
        t0 = datetime.fromisoformat(started)
        t1 = datetime.fromisoformat(finished)
    except ValueError:
        return None
    return round((t1 - t0).total_seconds(), 3)


def _dim_diff(before: dict, after: dict) -> dict[str, dict[str, float]]:
    """Per-dimension {before, after, delta} from two parsed verdict dim maps."""
    diff: dict[str, dict[str, float]] = {}
    for key in sorted(set(before) | set(after)):
        b = before.get(key)
        a = after.get(key)
        entry: dict[str, float] = {}
        if isinstance(b, (int, float)):
            entry["before"] = b
        if isinstance(a, (int, float)):
            entry["after"] = a
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            entry["delta"] = round(a - b, 3)
        diff[key] = entry
    return diff


class ProofPack:
    """Builds the proof-pack dict from a real store run (R3)."""

    @staticmethod
    def from_run(store: MemoryStore, run_id: int) -> dict[str, Any]:
        run = store.get_run(run_id)
        if run is None:
            raise ValueError(f"no run with id {run_id}")
        iters = store.iterations(run_id)
        if not iters:
            raise ValueError(f"run {run_id} has no iterations to prove")

        before, after = iters[0], iters[-1]
        pack: dict[str, Any] = {
            "before_grade": before.grade,
            "after_grade": after.grade,
            "dim_diff": _dim_diff(before.dims, after.dims),
            "iterations": len(iters),
            "convergence_status": run.status,
        }

        elapsed = _elapsed_seconds(run.started, run.finished)
        if elapsed is not None:
            pack["elapsed_seconds"] = elapsed

        # Token cost: sum any recorded per-iteration costs. Omit the field when
        # nothing was recorded -- never emit a placeholder (R3).
        costs = [it.token_cost for it in iters if it.token_cost is not None]
        if costs:
            pack["token_cost"] = sum(costs)

        regressions = [
            l["regression_test_ref"] for l in store.learnings(run_id) if l["regression_test_ref"]
        ]
        if regressions:
            pack["regression_tests"] = regressions

        return pack

    @staticmethod
    def is_improvement(pack: dict[str, Any]) -> bool:
        """True if the after-grade strictly beats the before-grade. A safety
        block or a no-gain run is not an improvement (used to keep an honest
        proof from being framed as a 'win')."""
        if pack.get("convergence_status") == "blocked_safety":
            return False
        return grade_rank(pack.get("after_grade", "")) > grade_rank(pack.get("before_grade", ""))
