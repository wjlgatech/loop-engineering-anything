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
from ..loop.integrity import (
    assert_loop_integrity,
    confirm_convergence,
    describe_gate_reason,
    gate_requires_confirmation,
)
from ..memory.store import MemoryStore
from ..preflight import missing_for_lane, missing_for_refine
from ..router import route


@dataclass(frozen=True)
class RunResult:
    run_id: int
    outcome: LoopOutcome
    # Anti-cognitive-surrender (U17, R10): a CONVERGED outcome is only
    # ``shippable`` once the human-confirm gate is satisfied. ``False`` means
    # "converged, but 'done' is still a claim until confirmed". For any
    # non-converged outcome this is ``False`` (nothing to ship).
    shippable: bool = False
    # Legible firing reason when the gate required confirmation (U5): the
    # borderline grade/score/dimension an out-of-band caller surfaces to the
    # human. ``None`` when no confirmation was owed (gate off / CI bypass / not
    # converged).
    gate_reason: str | None = None


def _apply_gate(
    outcome: LoopOutcome,
    config: Config,
    store: MemoryStore,
    run_id: int,
    *,
    scheduled: bool,
    confirmed: bool,
    when: str,
) -> tuple[bool, str | None]:
    """Apply the human-confirm gate to a finished outcome (U5/U17, R10).

    Only a CONVERGED result can be shippable; ``confirm_convergence`` is the sole
    shippability authority. When confirmation is actually owed, compose a legible
    firing reason and record the human verdict to the store for audit -- the
    recording is write-only and never feeds back into shippability (KTD5)."""
    if outcome.final_state is not LoopState.CONVERGED:
        return False, None
    shippable = confirm_convergence(config.gate, scheduled=scheduled, confirmed=confirmed)
    owed = gate_requires_confirmation(config.gate, scheduled=scheduled)
    if not owed:
        return shippable, None
    reason = describe_gate_reason(outcome.grade, outcome.score, outcome.dims)
    store.record_confirmation(run_id, confirmed=confirmed, reason=reason, created=when)
    return shippable, reason


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
    scheduled: bool = False,
    confirmed: bool = False,
    referee_paths=(),
    maker_write_paths=(),
    dev_seeds=None,
    heldout_seeds=None,
    upstream_context=None,
) -> RunResult:
    """Drive one unattended loop. Raises before any work starts if preflight,
    the credential gate, or the maker/checker integrity contract (U17) fails;
    returns a ``RunResult`` otherwise.

    ``upstream_context`` (plan-006 U3) carries upstream fleet-item outcomes routed
    into this run's briefs; ``None`` for a standalone run (identical to before).

    ``scheduled`` marks an unattended/scheduler-driven run: its CONVERGED result
    defaults to confirm-required regardless of CI (anti-surrender). ``confirmed``
    is the human's affirmative that satisfies the verification gate."""
    config = config or Config()
    budget = budget or config.budget
    validate_target(target)

    # U17 integrity contract (fail-closed, before any work — mirrors the
    # credential gate): maker ≠ checker, referee immutable to the maker, and a
    # disjoint held-out grade when the domain declares seeds (R6/R10/KTD6).
    assert_loop_integrity(
        refiner=refiner,
        judge=judge,
        referee_paths=referee_paths,
        maker_write_paths=maker_write_paths,
        dev_seeds=dev_seeds,
        heldout_seeds=heldout_seeds,
    )

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
            shippable=False,
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
        upstream_context=upstream_context,
    )
    outcome = controller.run(run_id, gen.tool_path, goal)
    when = datetime.now(timezone.utc).isoformat()
    shippable, gate_reason = _apply_gate(
        outcome, config, store, run_id, scheduled=scheduled, confirmed=confirmed, when=when
    )
    return RunResult(run_id, outcome, shippable=shippable, gate_reason=gate_reason)


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
    scheduled: bool = False,
    confirmed: bool = False,
    referee_paths=(),
    maker_write_paths=(),
    dev_seeds=None,
    heldout_seeds=None,
    upstream_context=None,
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

    # U17 integrity contract (fail-closed, before any work): maker ≠ checker,
    # referee immutable to the maker, disjoint held-out grade (R6/R10/KTD6).
    assert_loop_integrity(
        refiner=refiner,
        judge=judge,
        referee_paths=referee_paths,
        maker_write_paths=maker_write_paths,
        dev_seeds=dev_seeds,
        heldout_seeds=heldout_seeds,
    )

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
        upstream_context=upstream_context,
    )
    outcome = controller.run(run_id, tool_path, goal)
    # Stamp wall-clock end for the proof pack (elapsed = finished - started).
    # finish_run already set status; record_finished adds the timestamp the
    # controller doesn't own.
    when = datetime.now(timezone.utc).isoformat()
    store.record_finished(run_id, when)
    shippable, gate_reason = _apply_gate(
        outcome, config, store, run_id, scheduled=scheduled, confirmed=confirmed, when=when
    )
    return RunResult(run_id, outcome, shippable=shippable, gate_reason=gate_reason)
