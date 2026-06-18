"""Dependency-ordered fleet coordinator (plan-006 U2).

Turns the flat ``autonomous/parallel.py:run_parallel`` fan-out into a *coordinated*
fleet: items run in **topological waves** (ready items dispatched together, then
their dependents unlock) over the same worktree isolation, with cross-agent
lifecycle tracked in the store (U1).

Design seams kept thin so later units extend without re-touching this file:
  - ``classify`` maps a worker ``RunResult`` to the item's post-run status.
    The default here is a plain final-state map; U4 swaps in the escalation
    classifier (clean+shippable -> converged, else escalated).
  - feedback routing (U3) is a *pull*: before dispatching an item the coordinator
    gathers its dependencies' recorded outcomes and hands them to the runner as
    ``upstream_outcomes``, which the runner threads into the worker's brief.

Wrap-don't-fork (KTD1): this layer depends only on ``run_parallel``, the store,
and ``RunResult`` — the per-target ``LoopController`` is untouched.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from ..autonomous.parallel import ParallelTarget, run_parallel
from ..autonomous.runner import RunResult
from ..loop.controller import LoopOutcome, LoopState
from ..memory.fleet_state import FleetItem, FleetItemStatus, FleetRunStatus
from ..memory.store import MemoryStore
from .routing import gather_upstream_outcomes

# A status a dependency can end in that is NOT converged -> dependents can't run.
_FAILED_DEP = {
    FleetItemStatus.STOPPED,
    FleetItemStatus.BLOCKED,
    FleetItemStatus.ESCALATED,
    FleetItemStatus.BLOCKED_ON_DEP,
}


class FleetGraphError(ValueError):
    """A malformed fleet dependency graph (cycle or dangling edge). Fail-closed."""


def default_classify(result: RunResult) -> FleetItemStatus:
    """Map a worker outcome to a fleet-item status (U2 default; U4 overrides).

    Plain final-state map — no escalation logic here. A crashed/none result is
    treated by the caller, not this function."""
    state = result.outcome.final_state
    if state is LoopState.CONVERGED:
        return FleetItemStatus.CONVERGED
    if state is LoopState.BLOCKED_SAFETY:
        return FleetItemStatus.BLOCKED
    return FleetItemStatus.STOPPED


def outcome_summary(result: RunResult) -> dict:
    """The structured, JSON-able outcome recorded per item and routed to
    dependents (U3 reads this)."""
    o = result.outcome
    return {
        "grade": o.grade,
        "score": o.score,
        "final_state": o.final_state.value,
        "shippable": result.shippable,
        "gate_reason": result.gate_reason,
        "reason": o.reason,
    }


def apply_item_result(
    store: MemoryStore,
    item: FleetItem,
    res,
    classify: Callable[[RunResult], FleetItemStatus],
    *,
    on_fail: FleetItemStatus,
) -> RunResult | None:
    """Map one ``ParallelResult`` onto a fleet item's status + outcome. Shared by
    the coordinator's wave loop and escalation's single re-brief so the two never
    drift. ``on_fail`` is the status for a crashed/unexpected result (coordinator:
    ``STOPPED``; re-brief: ``ESCALATED``). The outcome is recorded **before** the
    status flips to converged, so a converged item always has its outcome present
    when a later wave's dependent pulls it (closes the converged-without-outcome
    window)."""
    if not res.ok or not isinstance(res.value, RunResult):
        msg = res.error or "no RunResult"
        store.set_item_status(item.id, on_fail)
        # Carry the error under both keys so `fleet escalations` / the report (which
        # read gate_reason|reason) show a cause instead of '-'.
        store.record_item_outcome(item.id, {"error": msg, "reason": msg})
        return None
    result = res.value
    store.record_item_outcome(item.id, outcome_summary(result))
    store.set_item_status(item.id, classify(result), run_id=result.run_id)
    return result


def _assert_acyclic(items: dict[str, FleetItem]) -> None:
    """Reject a cycle or a dangling dependency before any work starts (KTD3)."""
    for it in items.values():
        for dep in it.depends_on:
            if dep not in items:
                raise FleetGraphError(f"item {it.key!r} depends on unknown item {dep!r}")
    # Kahn's algorithm: if we can't remove every node, there is a cycle.
    indeg = {k: len(it.depends_on) for k, it in items.items()}
    queue = [k for k, d in indeg.items() if d == 0]
    seen = 0
    dependents: dict[str, list[str]] = {k: [] for k in items}
    for k, it in items.items():
        for dep in it.depends_on:
            dependents[dep].append(k)
    while queue:
        k = queue.pop()
        seen += 1
        for child in dependents[k]:
            indeg[child] -= 1
            if indeg[child] == 0:
                queue.append(child)
    if seen != len(items):
        raise FleetGraphError("fleet dependency graph has a cycle")


def default_fleet_runner(
    *,
    store: MemoryStore,
    fleet_goal: str | None,
    judge_adapter_override: str | None = None,
    judge_registry: str | None = None,
    refiner_kind: str = "chain",
    config=None,
) -> Callable[[FleetItem, str, list[dict]], RunResult]:
    """Build the default per-item runner: drive a real ``run_refine_loop`` inside
    each item's worktree, with the referee protected and ``upstream_context`` routed.

    Mirrors single ``run`` (U4): generate via the routed factory **into the item's
    worktree** (``workspace_root=worktree`` — a plain pass, not a rebase), resolve
    an out-of-jail adapter (U3), build deps (U1), then drive the existing
    ``run_refine_loop`` with ``referee_paths``/``maker_write_paths`` set so
    referee-immutability fires per worktree (KTD3)."""
    from ..adapters.judge import JudgeAdapterError, resolve_judge_adapter
    from ..autonomous import runner as _runner
    from ..bindings import build_loop_deps
    from ..config import Lane
    from ..router import route

    def _run(item: FleetItem, worktree: str, upstream: list[dict]) -> RunResult:
        goal = item.goal or fleet_goal or ""
        forced = Lane(item.lane) if item.lane else None
        decision = route(item.target, forced_lane=forced)
        factory = _runner._default_factories()[decision.factory]
        gen = factory.generate(decision.normalized_target, goal, worktree)
        if not gen.ok:
            return RunResult(
                run_id=None,  # no run row was created; never a phantom run 0
                outcome=LoopOutcome(
                    LoopState.STOPPED, grade="", reason="factory generation failed", iterations=0
                ),
                shippable=False,
            )
        adapter = resolve_judge_adapter(
            gen, override=judge_adapter_override, registry_dir=judge_registry
        )
        deps = build_loop_deps(
            tool_path=gen.tool_path, judge_adapter=adapter, refiner_kind=refiner_kind
        )
        return _runner.run_refine_loop(
            gen.tool_path,
            goal,
            judge=deps.judge,
            refiner=deps.refiner,
            compounder=deps.compounder,
            store=store,
            workspace_root=worktree,
            lane=decision.lane,
            config=config,
            referee_paths=[adapter],
            maker_write_paths=[gen.tool_path],
            upstream_context=upstream,
        )

    return _run


def run_fleet(
    store: MemoryStore,
    fleet_id: int,
    runner: Callable[[FleetItem, str, list[dict]], RunResult],
    *,
    repo_dir: str,
    worktrees_root: str,
    max_parallel: int = 2,
    classify: Callable[[RunResult], FleetItemStatus] = default_classify,
) -> FleetRunStatus:
    """Drive a fleet's items in dependency order over ``run_parallel``.

    ``runner(item, worktree_path, upstream_outcomes) -> RunResult`` runs one
    item's loop inside the per-item worktree. It is responsible for re-basing the
    worker's workspace_root onto ``worktree_path`` (mirroring
    ``Heartbeat.tick_parallel``) and passing ``upstream_outcomes`` to the worker
    as ``upstream_context`` (U3). The coordinator gathers those outcomes from the
    item's converged dependencies before dispatch (deterministic pull, no LLM).
    Returns the terminal fleet-run status (converged / awaiting_human / stopped).
    """
    items = {i.key: i for i in store.fleet_items(fleet_id)}
    _assert_acyclic(items)  # fail closed before any worktree is created

    while True:
        # One snapshot per wave: marking an item blocked_on_dep can't make it
        # ready (its dep is non-converged, so it fails the all-converged test),
        # so the ready set is computable from the same snapshot the marking used.
        items = {i.key: i for i in store.fleet_items(fleet_id)}
        converged = {k for k, i in items.items() if i.status is FleetItemStatus.CONVERGED}

        # Mark any pending item whose dependency ended non-converged as blocked_on_dep.
        for i in items.values():
            if i.status is FleetItemStatus.PENDING and any(
                items[d].status in _FAILED_DEP for d in i.depends_on
            ):
                store.set_item_status(i.id, FleetItemStatus.BLOCKED_ON_DEP)

        ready = [
            i
            for i in items.values()
            if i.status is FleetItemStatus.PENDING and all(d in converged for d in i.depends_on)
        ]
        if not ready:
            break

        for i in ready:
            store.set_item_status(i.id, FleetItemStatus.RUNNING)

        def _make_run(item: FleetItem) -> Callable[[str], RunResult]:
            # Pull this item's dependencies' recorded outcomes (U3) from the wave
            # snapshot already in hand -- no extra store read per item.
            upstream = gather_upstream_outcomes(store, fleet_id, item, items_by_key=items)

            def _run(worktree: str) -> RunResult:
                return runner(item, worktree, upstream)

            return _run

        results = run_parallel(
            [ParallelTarget(key=i.key, run=_make_run(i)) for i in ready],
            repo_dir=repo_dir,
            worktrees_root=worktrees_root,
            max_parallel=max_parallel,
        )

        for res in results:
            apply_item_result(
                store, items[res.key], res, classify, on_fail=FleetItemStatus.STOPPED
            )

    # Finalize the fleet run status.
    final = store.fleet_items(fleet_id)
    when = datetime.now(timezone.utc).isoformat()
    if final and all(i.status is FleetItemStatus.CONVERGED for i in final):
        status = FleetRunStatus.CONVERGED
    elif any(i.status is FleetItemStatus.ESCALATED for i in final):
        status = FleetRunStatus.AWAITING_HUMAN  # PARK: resumable, never a hang
    else:
        status = FleetRunStatus.STOPPED
    store.set_fleet_status(fleet_id, status, finished=when)
    return status
