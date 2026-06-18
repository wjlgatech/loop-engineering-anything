"""`loop-anything` CLI entrypoint (U1, R10).

Subcommands:
  preflight  Detect the four external dependencies.
  run        Route a target, generate the tool, and drive a real refine loop.
  status     Show recorded runs from the memory store.
  report     Render the research report for a run.
  fleet      Coordinate a fleet of self-improving loops.

The skill (skills/loop-anything/SKILL.md) and this CLI are the two agent-native
surfaces (R10). ``run`` gates on preflight, generates via the routed factory,
resolves an out-of-jail CLI-Judge adapter, and drives ``run_refine_loop`` end to
end with the referee protected from the maker.
"""

from __future__ import annotations

import json
import sys

import click

from .config import Lane
from .preflight import missing_for_lane, preflight
from .router import route


@click.group()
@click.version_option(package_name="loop-engineering-anything")
def main() -> None:
    """loop-engineering-anything: a self-improving loop orchestrator."""


@main.command("preflight")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@click.option(
    "--lane",
    type=click.Choice([lane.value for lane in Lane]),
    default=None,
    help="If set, exit non-zero when this lane's required tools are missing.",
)
def preflight_cmd(as_json: bool, lane: str | None) -> None:
    """Detect the four external dependencies."""
    statuses = preflight()
    if as_json:
        click.echo(
            json.dumps(
                [
                    {"key": s.key, "label": s.label, "available": s.available, "detail": s.detail}
                    for s in statuses
                ],
                indent=2,
            )
        )
    else:
        for s in statuses:
            mark = "ok " if s.available else "MISSING"
            click.echo(f"[{mark}] {s.label} -- {s.detail}")

    if lane is not None:
        missing = missing_for_lane(Lane(lane), statuses)
        if missing:
            names = ", ".join(m.label for m in missing)
            click.echo(f"\nLane '{lane}' is blocked -- missing: {names}", err=True)
            sys.exit(1)


@main.command("run")
@click.argument("target")
@click.option("--goal", required=True, help="High-level goal for the loop.")
@click.option(
    "--lane",
    type=click.Choice([lane.value for lane in Lane]),
    default=None,
    help="Force the target lane instead of auto-classifying.",
)
@click.option("--judge-adapter", "judge_adapter", default=None,
              help="Path to the CLI-Judge adapter (overrides auto-discovery). Must live outside the generated tool.")
@click.option("--refiner", "refiner_kind", type=click.Choice(["chain", "claude", "llm"]),
              default="chain", show_default=True, help="Refiner: chain (claude->LLM), claude, or llm.")
@click.option("--workspace", default="workspace", show_default=True, help="Workspace root for the generated tool.")
@click.option("--confirm/--no-confirm", default=False,
              help="Provide the human affirmative for the verification gate (attended runs only).")
@click.option("--scheduled", is_flag=True, help="Mark an unattended run (gate stays confirm-required).")
@click.option("--max-iterations", type=int, default=None, help="Override the loop's max iterations.")
def run_cmd(
    target: str, goal: str, lane: str | None, judge_adapter: str | None,
    refiner_kind: str, workspace: str, confirm: bool, scheduled: bool, max_iterations: int | None,
) -> None:
    """Route TARGET, generate the tool, and drive a real refine loop to Grade A."""
    # Anti-surrender: a scheduled (unattended) run cannot be pre-confirmed from the
    # CLI -- confirmation must come from a human after the run (R5).
    if scheduled and confirm:
        raise click.ClickException(
            "a scheduled run cannot be pre-confirmed from the CLI; confirmation must "
            "come from an attended human after the run completes."
        )

    import dataclasses

    from .adapters.judge import JudgeAdapterError, resolve_judge_adapter
    from .autonomous import runner as _runner
    from .bindings import build_loop_deps
    from .config import Config
    from .loop.controller import LoopState
    from .memory.store import MemoryStore

    decision = route(target, forced_lane=Lane(lane) if lane else None)
    click.echo(f"Lane: {decision.lane.value} ({decision.reason})")

    missing = missing_for_lane(decision.lane)
    if missing:
        names = ", ".join(m.label for m in missing)
        raise click.ClickException(f"Cannot run -- missing required tools: {names}")

    # Generate the tool, then resolve the judge adapter against the produced tool
    # and drive the EXISTING run_refine_loop (KTD2: no run_loop changes; the
    # adapter is only knowable post-generate).
    import os

    os.makedirs(workspace, exist_ok=True)
    factory = _runner._default_factories()[decision.factory]
    gen = factory.generate(decision.normalized_target, goal, workspace)
    if not gen.ok:
        raise click.ClickException(
            f"factory generation failed on the {decision.lane.value} lane: "
            f"{(gen.logs or '').strip()[:300] or 'no logs'}"
        )

    try:
        adapter = resolve_judge_adapter(gen, override=judge_adapter)
    except JudgeAdapterError as e:
        raise click.ClickException(str(e))

    deps = build_loop_deps(
        tool_path=gen.tool_path, judge_adapter=adapter, refiner_kind=refiner_kind
    )
    if deps.provider_env_keys and not any(os.environ.get(k) for k in deps.provider_env_keys):
        click.echo(
            f"warning: no LLM provider key set ({', '.join(deps.provider_env_keys)}); "
            "the fallback refiner will degrade to a local (Ollama) rung.",
            err=True,
        )

    config = Config()
    if max_iterations is not None:
        config = dataclasses.replace(
            config, budget=dataclasses.replace(config.budget, max_iterations=max_iterations)
        )

    store = MemoryStore.default()
    try:
        result = _runner.run_refine_loop(
            gen.tool_path,
            goal,
            judge=deps.judge,
            refiner=deps.refiner,
            compounder=deps.compounder,
            store=store,
            workspace_root=workspace,
            lane=decision.lane,
            config=config,
            referee_paths=[adapter],
            maker_write_paths=[gen.tool_path],
            scheduled=scheduled,
            confirmed=confirm,
        )
    except RuntimeError as e:  # preflight / credential / integrity failures
        raise click.ClickException(str(e))

    o = result.outcome
    refiner_used = getattr(deps.refiner, "last_refiner", None)
    converged = o.final_state is LoopState.CONVERGED
    click.echo(
        f"Run #{result.run_id}: {o.final_state.value} grade={o.grade or '-'} "
        f"over {o.iterations} iter(s)"
        + (f" via {refiner_used}" if refiner_used else "")
    )
    if converged:
        click.echo(
            f"shippable={result.shippable}"
            + (f" -- gate: {result.gate_reason}" if result.gate_reason else "")
        )
    click.echo(f"Inspect: loopeng report {result.run_id}")


@main.command("judge-variance")
@click.argument("tool_path")
@click.option("--adapter", required=True, help="CLI-Judge tool adapter path.")
@click.option("-k", "samples", default=5, show_default=True, help="Number of re-judges.")
def judge_variance_cmd(tool_path: str, adapter: str, samples: int) -> None:
    """Re-judge an unchanged TOOL_PATH K times to measure grade stability (P0 #2)."""
    from .adapters.judge import CLIJudge, probe_grade_variance

    report = probe_grade_variance(CLIJudge(adapter), tool_path, k=samples)
    click.echo(f"grades: {report.grades}")
    click.echo(f"scores: {report.scores}")
    click.echo(f"grade stable: {report.grade_stable}")
    click.echo(f"score spread: {report.score_spread}")
    if not report.grade_stable:
        click.echo(
            f"\nGrades are NOT stable. Set Budget.min_score_gain >= "
            f"{report.recommended_min_score_gain} so the loop ignores sub-noise jitter."
        )


@main.command("status")
def status_cmd() -> None:
    """Show recorded runs from the memory store."""
    from .memory.store import MemoryStore

    store = MemoryStore.default()
    runs = store.list_runs()
    if not runs:
        click.echo("No runs recorded yet.")
        return
    for r in runs:
        click.echo(f"#{r.id}  {r.target}  [{r.lane}]  status={r.status}  grade={r.final_grade or '-'}")


@main.command("report")
@click.argument("run_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def report_cmd(run_id: int, as_json: bool) -> None:
    """Render the research report for RUN_ID."""
    from .autonomous.report import render_report
    from .memory.store import MemoryStore

    store = MemoryStore.default()
    click.echo(render_report(store, run_id, as_json=as_json))


@main.group("fleet")
def fleet_grp() -> None:
    """Coordinate a fleet of self-improving loops (plan-006)."""


@fleet_grp.command("run")
@click.argument("spec_path")
@click.option("--goal", default=None, help="Top-level goal for the fleet.")
def fleet_run_cmd(spec_path: str, goal: str | None) -> None:
    """Parse a fleet SPEC (JSON) and materialize the fleet run."""
    import json
    from datetime import datetime, timezone

    from .memory.store import MemoryStore
    from .orchestration.spec import FleetSpecError, materialize_fleet, parse_fleet_spec

    with open(spec_path, encoding="utf-8") as fh:
        data = json.load(fh)
    try:
        items = parse_fleet_spec(data)
    except FleetSpecError as exc:
        raise click.ClickException(str(exc)) from exc

    store = MemoryStore.default()
    started = datetime.now(timezone.utc).isoformat()
    fleet_id = materialize_fleet(store, goal or data.get("goal"), items, started)
    click.echo(f"Fleet #{fleet_id} created with {len(items)} items.")
    # Live per-item execution drives run_loop per item, which needs the factory
    # adapters (same gate as `run`). The coordinator (run_fleet) is exercised in
    # tests; inspect a materialized fleet with `fleet status` / `fleet report`.
    click.echo(
        "Live per-item execution requires the factory adapters (see `run`). "
        "Inspect this fleet with `fleet status` / `fleet report`."
    )


@fleet_grp.command("status")
@click.argument("fleet_id", type=int)
def fleet_status_cmd(fleet_id: int) -> None:
    """Show a fleet run's items and their lifecycle status."""
    from .memory.store import MemoryStore

    store = MemoryStore.default()
    fleet = store.get_fleet(fleet_id)
    if fleet is None:
        click.echo(f"No fleet #{fleet_id}.")
        return
    click.echo(f"Fleet #{fleet_id}  status={fleet.status.value}  goal={fleet.goal or '-'}")
    for i in store.fleet_items(fleet_id):
        dep = f"  deps={','.join(i.depends_on)}" if i.depends_on else ""
        click.echo(f"  - {i.key:<16} {i.status.value}{dep}")


@fleet_grp.command("report")
@click.argument("fleet_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def fleet_report_cmd(fleet_id: int, as_json: bool) -> None:
    """Aggregated fleet report: per-item lifecycle, grades, escalations."""
    from .memory.store import MemoryStore
    from .orchestration.fleet_report import build_fleet_report, render_fleet_report

    store = MemoryStore.default()
    report = build_fleet_report(store, fleet_id)
    if report is None:
        click.echo(f"No fleet #{fleet_id}.")
        return
    click.echo(render_fleet_report(report, as_json=as_json))


@fleet_grp.command("escalations")
@click.argument("fleet_id", type=int)
def fleet_escalations_cmd(fleet_id: int) -> None:
    """List the items awaiting a human, with their reasons."""
    from .memory.store import MemoryStore

    store = MemoryStore.default()
    if store.get_fleet(fleet_id) is None:
        click.echo(f"No fleet #{fleet_id}.")
        return
    esc = store.escalations(fleet_id)
    if not esc:
        click.echo("No escalations.")
        return
    for i in esc:
        reason = (i.outcome or {}).get("gate_reason") or (i.outcome or {}).get("reason") or "-"
        click.echo(f"  - {i.key}: {reason}")


@main.command("showcase")
@click.option("--out", default="showcase.html", show_default=True, help="Output HTML path.")
@click.option(
    "--base-url",
    default="",
    help="Prefix for doc links (e.g. a GitHub blob URL) so report/recipe links resolve when hosted.",
)
def showcase_cmd(out: str, base_url: str) -> None:
    """Generate the self-contained HTML demo catalog."""
    from .demos.registry import Registry
    from .showcase.generate import render_catalog

    reg = Registry.load()
    with open(out, "w") as fh:
        fh.write(render_catalog(reg, base_url=base_url))
    click.echo(f"Showcase written to {out} ({len(reg.demos())} demos, {len(reg.recipes())} recipes).")


@main.group("demo")
def demo_grp() -> None:
    """Manage community demos (list / show / validate / record / run)."""


@demo_grp.command("list")
@click.option("--domain", default=None, help="Filter to one domain.")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def demo_list_cmd(domain: str | None, as_json: bool) -> None:
    """List registered demos."""
    from .demos.registry import Registry

    reg = Registry.load()
    rows = []
    for m in reg.manifests.values():
        if domain and m.domain != domain:
            continue
        result = reg.result_for(m)
        rows.append(
            {"id": m.id, "domain": m.domain, "kind": m.kind, "source": result.source if result else "none"}
        )
    if as_json:
        click.echo(json.dumps(rows, indent=2))
    else:
        for r in rows:
            click.echo(f"{r['id']:<22} [{r['kind']}]  {r['domain']}  ({r['source']})")


@demo_grp.command("show")
@click.argument("demo_id")
def demo_show_cmd(demo_id: str) -> None:
    """Show one demo's manifest and result."""
    from .demos.registry import Registry

    reg = Registry.load()
    m = reg.manifests.get(demo_id)
    if m is None:
        raise click.ClickException(f"no demo with id {demo_id!r}. Try `loop-anything demo list`.")
    click.echo(f"{m.id}  [{m.kind}]\n  domain: {m.domain}\n  target: {m.target} ({m.lane.value})\n  goal: {m.goal}")
    if m.required_env:
        click.echo(f"  required_env: {', '.join(m.required_env)}")
    result = reg.result_for(m)
    if result:
        click.echo(f"  result: {result.source}  {' -> '.join(result.grade_trajectory)}  ({result.convergence_status})")


@demo_grp.command("validate")
def demo_validate_cmd() -> None:
    """Validate every manifest + result fixture (the CI gate). Exit 1 on any failure."""
    from .demos.manifest import ManifestError
    from .demos.registry import Registry

    try:
        reg = Registry.load()
        for m in reg.manifests.values():
            reg.result_for(m)  # loads + schema-validates the fixture when present
    except ManifestError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"OK: {len(reg.manifests)} manifests valid.")


def _record_run(reg, store, demo_id: str, run_id: int, *, proof: dict | None = None) -> dict:
    """Build, validate, and write a live_verified fixture + report for a run.

    The single write path to live_verified status (KTD2). ``proof`` is the
    optional proof pack (``demo proof`` supplies it; bare ``demo record`` does
    not) -- when present it is embedded so the showcase can headline before/after.
    """
    from . import __version__
    from .autonomous.report import render_report
    from .demos.result import from_dict as result_from_dict

    run = store.get_run(run_id)
    if run is None:
        raise click.ClickException(f"no run #{run_id} in the memory store.")

    payload = {
        "demo_id": demo_id,
        "source": "live_verified",
        "grade_trajectory": store.grade_trajectory(run_id) or [run.final_grade or "F"],
        "final_grade": run.final_grade or "F",
        "convergence_status": run.status,
        "report_ref": f"{demo_id}.report.md",
        "engine_version": __version__,
    }
    if proof is not None:
        payload["proof"] = proof
    result_from_dict(payload)  # validate before writing
    results_dir = reg.demos_dir / "results"
    results_dir.mkdir(exist_ok=True)
    (results_dir / f"{demo_id}.json").write_text(json.dumps(payload, indent=2))
    (results_dir / f"{demo_id}.report.md").write_text(render_report(store, run_id))
    return payload


@demo_grp.command("record")
@click.argument("demo_id")
@click.option("--from", "run_id", type=int, required=True, help="Run-history id to snapshot.")
def demo_record_cmd(demo_id: str, run_id: int) -> None:
    """Snapshot a real run into a live_verified fixture + persisted report."""
    from .demos.registry import Registry
    from .memory.store import MemoryStore

    reg = Registry.load()
    if demo_id not in reg.manifests:
        raise click.ClickException(f"no demo with id {demo_id!r}.")
    store = MemoryStore.default()
    payload = _record_run(reg, store, demo_id, run_id)
    click.echo(
        f"Recorded {demo_id} from run #{run_id} "
        f"({payload['final_grade']}, {payload['convergence_status']})."
    )


def _run_generator(manifest, workspace: str):
    """Attempt the real generate step via the generator's Claude Code skill.

    Both generators are Claude Code skills driven by `claude -p`:
      service lane  -> /printing-press <target>
      codebase lane -> /cli-anything <target>
    This really runs today; while headless quota is exhausted it returns the
    upstream usage-limit error, and it Just Works once quota/a key is available.
    """
    from .config import Lane
    from .adapters.safety import run_tool

    skill = "/printing-press" if manifest.lane is Lane.SERVICE else "/cli-anything"
    prompt = f"{skill} {manifest.target}\nGoal: {manifest.goal}"
    return run_tool(
        ["claude", "-p", prompt, "--permission-mode", "bypassPermissions"],
        cwd=workspace,
        timeout=60 * 60,
    )


@demo_grp.command("run")
@click.argument("demo_id")
@click.option("--workspace", default=None, help="Where to generate the tool (default .loopeng/<id>).")
def demo_run_cmd(demo_id: str, workspace: str | None) -> None:
    """Generate + (when an adapter exists) judge + record a demo, live."""
    import os

    from .demos.registry import Registry
    from .preflight import missing_for_lane

    reg = Registry.load()
    m = reg.manifests.get(demo_id)
    if m is None:
        raise click.ClickException(f"no demo with id {demo_id!r}.")
    if not m.runnable:
        raise click.ClickException(f"{demo_id} is a recipe, not a runnable demo.")
    missing = missing_for_lane(m.lane)
    if missing:
        raise click.ClickException(f"missing tools: {', '.join(x.label for x in missing)}")

    workspace = workspace or os.path.join(".loopeng", demo_id)
    os.makedirs(workspace, exist_ok=True)
    click.echo(f"Generating {demo_id} ({m.lane.value} lane) into {workspace}/ ...")
    res = _run_generator(m, workspace)
    if not res.ok:
        detail = (res.stderr or res.stdout or "generator failed").strip()[:500]
        raise click.ClickException(f"generation failed for {m.target}:\n{detail}")

    adapter = reg.demos_dir / "adapters" / f"{demo_id}.py"
    if adapter.exists():
        click.echo(
            f"Generated into {workspace}/. Grade it: "
            f"`cli-judge run --adapter {adapter} --suite full`, then "
            f"`loop-anything demo record {demo_id} --from <run_id>` to publish a live_verified card."
        )
    else:
        click.echo(
            f"Generated into {workspace}/. To grade + record a live_verified result, add a "
            f"CLI-Judge adapter at demos/adapters/{demo_id}.py, then re-run."
        )


@demo_grp.command("proof")
@click.argument("demo_id")
@click.option("--catalog", required=True, help="Catalog key: cli-anything | printing-press.")
@click.option("--name", "entry_name", required=True, help="Catalog entry/package name to adopt.")
@click.option("--sha", required=True, help="Full 40-char commit SHA to pin the baseline (KTD7).")
@click.option("--install-kind", required=True, help="pip_git_subdir | pp_binary.")
@click.option("--workspace", default=None, help="Where to adopt the tool (default .loopeng/proof/<id>).")
@click.option("--required-env", multiple=True, help="Env var names the adopted tool needs.")
@click.option("--refiner", type=click.Choice(["claude", "llm"]), default="claude",
              help="Refine engine: 'claude' (/ce-work via claude -p) or 'llm' "
                   "(free-tier fallback chain — no claude quota).")
@click.option("--dry-run", is_flag=True, help="Print the adopt + loop plan; write nothing.")
def demo_proof_cmd(
    demo_id: str,
    catalog: str,
    entry_name: str,
    sha: str,
    install_kind: str,
    workspace: str | None,
    required_env: tuple[str, ...],
    refiner: str,
    dry_run: bool,
) -> None:
    """Adopt a catalog CLI as a baseline, run the refine loop, and record a
    live_verified proof pack (before/after). The reproducible proof pipeline (U4).

    Honest by construction: a card flips to live_verified ONLY via the shared
    record path against a real run (KTD2), and a safety-blocked run is recorded
    as blocked_safety, never as a passing proof (R6).
    """
    import os

    from .adopt import AdoptSpec, adopt
    from .config import Lane
    from .demos.registry import Registry
    from .preflight import missing_for_refine

    reg = Registry.load()
    m = reg.manifests.get(demo_id)
    if m is None:
        raise click.ClickException(f"no demo with id {demo_id!r}.")
    if not m.runnable:
        raise click.ClickException(f"{demo_id} is a recipe, not a runnable demo.")

    workspace = workspace or os.path.join(".loopeng", "proof", demo_id)
    spec = AdoptSpec(
        catalog=catalog,
        name=entry_name,
        sha=sha,
        install_kind=install_kind,
        required_env=tuple(required_env),
    )

    if dry_run:
        click.echo(
            f"[dry-run] proof plan for {demo_id}:\n"
            f"  adopt:  {catalog}:{entry_name}@{sha[:12]} ({install_kind}) -> {workspace}/\n"
            f"  loop:   refine-only on the {m.lane.value} lane, goal={m.goal!r}\n"
            f"  refiner: {refiner}\n"
            f"  record: live_verified + proof pack via `demo record` (only on a real run)."
        )
        return

    missing = missing_for_refine(refiner=refiner)
    if missing:
        raise click.ClickException(f"missing tools for a refine run: {', '.join(x.label for x in missing)}")

    click.echo(f"Adopting {catalog}:{entry_name}@{sha[:12]} into {workspace}/ ...")
    adopted = adopt(spec, workspace)
    if not adopted.ok:
        raise click.ClickException(f"adoption failed: {adopted.error or adopted.logs[:300]}")

    run_id = _drive_proof_loop(adopted.tool_path, m, workspace, refiner)
    _finish_proof(reg, demo_id, run_id, adopted.resolved_sha)


def _drive_proof_loop(tool_path: str, manifest, workspace: str, refiner: str = "claude") -> int:
    """Run the refine-only loop on an adopted tool; returns the run id.

    ``refiner='claude'`` drives `/ce-work` via `claude -p` (the documented brain).
    ``refiner='llm'`` drives the provider-agnostic fallback-chain LLM refiner --
    no claude, no quota -- and skips the `/ce-compound` inner step (learnings are
    still recorded to the store for the proof pack)."""
    from .adapters.judge import CLIJudge
    from .autonomous.runner import run_refine_loop
    from .demos.registry import Registry
    from .memory.store import MemoryStore

    reg = Registry.load()
    adapter = reg.demos_dir / "adapters" / f"{manifest.id}.py"
    if not adapter.exists():
        raise click.ClickException(
            f"no CLI-Judge adapter at demos/adapters/{manifest.id}.py -- add one (U5) before proving."
        )

    if refiner == "llm":
        from .adapters.llm_refiner import FallbackLLMRefiner
        refiner_impl = FallbackLLMRefiner()
        compounder_impl = None  # store-only learnings; no claude /ce-compound
    else:
        from .adapters.compound_engineering import ClaudeCodeCompounder, ClaudeCodeRefiner
        refiner_impl = ClaudeCodeRefiner()
        compounder_impl = ClaudeCodeCompounder(tool_path)

    store = MemoryStore.default()
    result = run_refine_loop(
        tool_path,
        manifest.goal,
        judge=CLIJudge(adapter_path=str(adapter)),
        refiner=refiner_impl,
        compounder=compounder_impl,
        store=store,
        workspace_root=workspace,
        lane=manifest.lane,
        target_label=manifest.target,
    )
    return result.run_id


def _finish_proof(reg, demo_id: str, run_id: int, resolved_sha: str | None) -> None:
    """Build the proof pack and record a live_verified fixture (honest status)."""
    from .memory.store import MemoryStore
    from .proof import ProofPack

    store = MemoryStore.default()
    proof = ProofPack.from_run(store, run_id)
    if resolved_sha:
        proof["baseline_source_sha"] = resolved_sha
    payload = _record_run(reg, store, demo_id, run_id, proof=proof)

    status = payload["convergence_status"]
    if status == "blocked_safety":
        click.echo(f"Recorded {demo_id}: BLOCKED_SAFETY -- honest result, not a passing proof (R6).")
    elif ProofPack.is_improvement(proof):
        click.echo(
            f"Recorded {demo_id}: {proof['before_grade']} -> {proof['after_grade']} "
            f"over {proof['iterations']} iters (live_verified)."
        )
    else:
        click.echo(
            f"Recorded {demo_id}: no grade gain ({proof['before_grade']} -> {proof['after_grade']}, "
            f"{status}) -- honest result, recorded as-is."
        )


@main.group("schedule")
def schedule_grp() -> None:
    """Register recurring loops and inspect their cadence (U14, R7).

    Durable: registrations live in SQLite and survive a restart ("going to the
    beach" -> "always running"). Execution rides the same injected runner the
    autonomous loop uses; `tick` lists what is due now (live execution lands with
    the generate adapters, exactly as `run`)."""


@schedule_grp.command("add")
@click.argument("target")
@click.option("--interval", "interval_seconds", type=float, required=True,
              help="Minimum seconds between runs for this target.")
@click.option("--goal", default="", help="High-level goal passed to the loop.")
@click.option("--lane", type=click.Choice([lane.value for lane in Lane]), default=None,
              help="Force the target lane instead of auto-classifying.")
@click.option("--domain", default=None, help="Force a registered domain by name.")
def schedule_add_cmd(target: str, interval_seconds: float, goal: str, lane: str | None, domain: str | None) -> None:
    """Register TARGET to run on a recurring cadence."""
    from .memory.store import MemoryStore
    from .scheduler import Heartbeat

    hb = Heartbeat(MemoryStore.default(), runner=lambda fire: -1)
    try:
        hb.schedule(target, interval_seconds=interval_seconds, goal=goal, lane=lane, domain=domain)
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"Scheduled {target!r} every {interval_seconds:g}s (goal={goal!r}).")


@schedule_grp.command("list")
def schedule_list_cmd() -> None:
    """Show registered schedules and when each last fired."""
    from .memory.store import MemoryStore

    entries = MemoryStore.default().schedules()
    if not entries:
        click.echo("No schedules registered.")
        return
    for e in entries:
        last = "never" if e.last_fired is None else f"{e.last_fired:.0f}"
        click.echo(
            f"{e.target}  every {e.interval_seconds:g}s  last_fired={last}  "
            f"last_run={e.last_run_id or '-'}  goal={e.goal or '-'}"
        )


@schedule_grp.command("remove")
@click.argument("target")
def schedule_remove_cmd(target: str) -> None:
    """Unregister TARGET from the schedule."""
    from .memory.store import MemoryStore

    removed = MemoryStore.default().remove_schedule(target)
    click.echo(f"Removed {target!r}." if removed else f"{target!r} was not scheduled.")


@schedule_grp.command("tick")
def schedule_tick_cmd() -> None:
    """List the targets due to run right now (one heartbeat, no execution).

    Live execution rides the injected runner used by the autonomous loop; until
    the generate adapters are wired (same gate as `run`), `tick` reports the due
    set so an operator/cron can see the cadence without fabricating a run."""
    import time

    from .memory.store import MemoryStore
    from .scheduler import Heartbeat

    hb = Heartbeat(MemoryStore.default(), runner=lambda fire: -1)
    due = hb.due(now=time.time())
    if not due:
        click.echo("Nothing due.")
        return
    click.echo(f"{len(due)} target(s) due:")
    for e in due:
        click.echo(f"  {e.target}  (goal={e.goal or '-'})")


if __name__ == "__main__":  # pragma: no cover
    main()
