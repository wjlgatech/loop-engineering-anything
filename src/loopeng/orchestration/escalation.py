"""Fleet-level human-efficiency escalation (plan-006 U4).

Only high-judgment forks reach the human — a worker blocked on safety, a
converged-but-gated result (confirmation owed), or a worker stuck (stopped) after
its pivots are exhausted. A clean converged-and-shippable item proceeds silently.

The fleet NEVER auto-merges a blocked or unconfirmed item: ``confirm_convergence``
(read via the worker's ``RunResult.shippable``) stays the sole shippability
authority — the R10 anti-cognitive-surrender guarantee (plan-005 U5), lifted to
the fleet (KTD5).
"""

from __future__ import annotations

from collections.abc import Callable

from ..autonomous.parallel import ParallelTarget, run_parallel
from ..autonomous.runner import RunResult
from ..loop.controller import LoopState
from ..memory.fleet_state import FleetItem, FleetItemStatus
from ..memory.store import MemoryStore
from .coordinator import apply_item_result
from .routing import gather_upstream_outcomes


def classify_with_escalation(result: RunResult) -> FleetItemStatus:
    """The escalation classifier the coordinator plugs in (replaces the U2 default).

    - converged AND shippable -> ``converged`` (auto-proceeds, unlocks dependents)
    - converged but NOT shippable (gated; confirmation owed) -> ``escalated``
    - ``BLOCKED_SAFETY`` -> ``escalated`` (never auto-merged)
    - stopped / anything else (stuck, pivots exhausted) -> ``escalated``
    """
    if result.outcome.final_state is LoopState.CONVERGED:
        return FleetItemStatus.CONVERGED if result.shippable else FleetItemStatus.ESCALATED
    return FleetItemStatus.ESCALATED


def rebrief_item(
    store: MemoryStore,
    fleet_id: int,
    item_key: str,
    human_note: str,
    runner: Callable[[FleetItem, str, list[dict]], RunResult],
    *,
    repo_dir: str,
    worktrees_root: str,
    classify: Callable[[RunResult], FleetItemStatus] = classify_with_escalation,
) -> RunResult | None:
    """"Talk to a worker": re-run a single escalated item with a human note added
    to its brief context, updating the **existing** item row in place (run_id
    replaced, status reset to running first). Does not re-run the fleet.

    Returns the new ``RunResult``, or ``None`` if the re-run crashed (the item is
    returned to ``escalated``). Phase A staleness: dependents that already ran
    against this item's prior output are NOT auto-re-routed — surfaced, not
    silently corrected.
    """
    item = {i.key: i for i in store.fleet_items(fleet_id)}.get(item_key)
    if item is None:
        raise KeyError(f"no fleet item {item_key!r} in fleet {fleet_id}")
    if item.status is not FleetItemStatus.ESCALATED:
        raise ValueError(f"item {item_key!r} is not escalated (status {item.status.value})")

    store.set_item_status(item.id, FleetItemStatus.RUNNING)
    upstream = gather_upstream_outcomes(store, fleet_id, item) + [
        {"item": "human", "note": human_note}
    ]

    def _run(worktree: str) -> RunResult:
        return runner(item, worktree, upstream)

    [res] = run_parallel(
        [ParallelTarget(key=item.key, run=_run)],
        repo_dir=repo_dir,
        worktrees_root=worktrees_root,
        max_parallel=1,
    )
    # Shared result-mapping with the coordinator; on a crashed re-run the item
    # returns to escalated (not stopped), so the human can try again.
    return apply_item_result(store, item, res, classify, on_fail=FleetItemStatus.ESCALATED)
