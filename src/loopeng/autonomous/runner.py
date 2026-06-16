"""Autonomous "going to the beach" runner (U8, R9).

Wires preflight -> route -> factory -> controller into one unattended call.
Shell against the real adapters with the guard rails the doc-review required:

  - preflight gate: refuse to start if a tool required for the lane is missing.
  - credential gate (S-1): required env vars must be set; values are never
    logged or persisted.
  - filesystem boundary (S-4): the generated tool lives under a workspace root;
    git checkpoints there make each iteration recoverable and roll back cleanly.

The controller core it drives is already validated against recorded verdicts;
this module adds the live wiring. Factories/judge/checkpoint are injectable so
the wiring is testable without the real tools installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from ..adapters.base import Checkpoint, Compounder, Factory, Judge, Refiner
from ..adapters.cli_anything import CLIAnythingFactory
from ..adapters.printing_press import PrintingPressFactory
from ..adapters.safety import run_tool, validate_target, within_workspace
from ..config import Budget, Config, Lane
from ..loop.checkpoint import GitCheckpoint
from ..loop.controller import LoopController, LoopOutcome, LoopState
from ..memory.store import MemoryStore
from ..preflight import missing_for_lane, missing_for_refine
from ..router import route


@dataclass(frozen=True)
class RunResult:
    run_id: int
    outcome: LoopOutcome


def _default_factories() -> dict[str, Factory]:
    return {"printing-press": PrintingPressFactory(), "cli-anything": CLIAnythingFactory()}


def _check_credentials(config: Config) -> None:
    missing = [name for name in config.required_env if not os.environ.get(name)]
    if missing:
        # Names only -- never echo values.
        raise RuntimeError(f"missing required credential env vars: {', '.join(missing)}")


def _ensure_git_repo(path: str) -> None:
    if not os.path.isdir(os.path.join(path, ".git")):
        run_tool(["git", "-C", path, "init", "-q"])
        run_tool(["git", "-C", path, "config", "user.email", "loop@local"])
        run_tool(["git", "-C", path, "config", "user.name", "loop-engineering-anything"])


def run_loop(
    target: str,
    goal: str,
    *,
    judge: Judge,
    refiner: Refiner,
    compounder: Compounder,
    store: MemoryStore,
    config: Config | None = None,
    budget: Budget | None = None,
    lane: Lane | None = None,
    workspace_root: str = "workspace",
    factories: dict[str, Factory] | None = None,
    checkpoint: Checkpoint | None = None,
    check_missing=missing_for_lane,
) -> RunResult:
    """Drive one unattended loop. Raises before any work starts if preflight or
    the credential gate fails; returns a ``RunResult`` otherwise."""
    config = config or Config()
    budget = budget or config.budget
    validate_target(target)

    decision = route(target, forced_lane=lane)

    blocked = check_missing(decision.lane)
    if blocked:
        names = ", ".join(b.label for b in blocked)
        raise RuntimeError(f"preflight: cannot run on the {decision.lane.value} lane -- missing: {names}")

    _check_credentials(config)

    factories = factories or _default_factories()
    factory = factories[decision.factory]

    os.makedirs(workspace_root, exist_ok=True)
    gen = factory.generate(decision.normalized_target, goal, workspace_root)
    started = datetime.now(timezone.utc).isoformat()
    run_id = store.create_run(decision.normalized_target, decision.lane.value, goal, started)

    if not gen.ok:
        store.finish_run(run_id, LoopState.STOPPED.value, None)
        return RunResult(
            run_id,
            LoopOutcome(LoopState.STOPPED, grade="", reason="factory generation failed", iterations=0),
        )

    if checkpoint is None:
        _ensure_git_repo(gen.tool_path)
        checkpoint = GitCheckpoint(gen.tool_path)

    controller = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=compounder,
        checkpoint=checkpoint,
        store=store,
        budget=budget,
    )
    outcome = controller.run(run_id, gen.tool_path, goal)
    return RunResult(run_id, outcome)


def run_refine_loop(
    tool_path: str,
    goal: str,
    *,
    judge: Judge,
    refiner: Refiner,
    compounder: Compounder | None,
    store: MemoryStore,
    workspace_root: str,
    lane: Lane = Lane.SERVICE,
    config: Config | None = None,
    budget: Budget | None = None,
    checkpoint: Checkpoint | None = None,
    check_missing=missing_for_refine,
    target_label: str | None = None,
) -> RunResult:
    """Drive the loop on an **already-present** tool (proof pipeline, U2).

    The "refine-only" entrypoint: there is no generate step. ``tool_path`` is an
    adopted catalog CLI (or an in-repo target) that already lives under
    ``workspace_root``. The controller's *initial* judge of that tool is the
    recorded "before" baseline (KTD1 -- controller is unchanged). Preflight gates
    on the judge + refinement engine only (no factory). Wall-clock is measured
    around the loop and stamped via ``store.record_finished`` for the proof pack.
    """
    config = config or Config()
    budget = budget or config.budget

    # Filesystem jail: the tool must already live inside the workspace (S-4).
    if not within_workspace(tool_path, workspace_root):
        raise ValueError(f"tool_path is outside the workspace root: {tool_path!r}")

    blocked = check_missing()
    if blocked:
        names = ", ".join(b.label for b in blocked)
        raise RuntimeError(f"preflight: cannot run a refine loop -- missing: {names}")

    _check_credentials(config)

    label = target_label or tool_path
    started = datetime.now(timezone.utc).isoformat()
    run_id = store.create_run(label, lane.value, goal, started)

    if checkpoint is None:
        _ensure_git_repo(tool_path)
        checkpoint = GitCheckpoint(tool_path)

    # Wrap the injected compounder so every accepted-fix learning is recorded to
    # the store (the proof pack's regression_tests field reads from there). The
    # real /ce-compound binding rides along as the inner compounder.
    from ..proof import StoreBackedCompounder

    store_compounder = StoreBackedCompounder(store, run_id, inner=compounder)

    controller = LoopController(
        judge=judge,
        refiner=refiner,
        compounder=store_compounder,
        checkpoint=checkpoint,
        store=store,
        budget=budget,
    )
    outcome = controller.run(run_id, tool_path, goal)
    # Stamp wall-clock end for the proof pack (elapsed = finished - started).
    # finish_run already set status; record_finished adds the timestamp the
    # controller doesn't own.
    store.record_finished(run_id, datetime.now(timezone.utc).isoformat())
    return RunResult(run_id, outcome)
