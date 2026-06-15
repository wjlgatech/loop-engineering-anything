"""`loop-anything` CLI entrypoint (U1, R10).

Subcommands:
  preflight  Detect the four external dependencies.
  run        Route a target and (when factories are wired) drive the loop.
  status     Show recorded runs from the memory store.
  report     Render the research report for a run.

The skill (skills/loop-anything/SKILL.md) and this CLI are the two agent-native
surfaces (R10). Preflight is fully wired; ``run`` gates on preflight and routes,
then stops where the real factory adapters (U4/U5) are not yet bound.
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
def run_cmd(target: str, goal: str, lane: str | None) -> None:
    """Route TARGET and (when factories are wired) drive the loop."""
    decision = route(target, forced_lane=Lane(lane) if lane else None)
    click.echo(f"Lane: {decision.lane.value} ({decision.reason})")

    missing = missing_for_lane(decision.lane)
    if missing:
        names = ", ".join(m.label for m in missing)
        raise click.ClickException(f"Cannot run -- missing required tools: {names}")

    # The factory adapters (U4) and judge adapter (U5) bind to the real external
    # tools and are built in a later unit; the controller core (U6) is exercised
    # via tests against injectable Judge/Refiner protocols until then.
    raise click.ClickException(
        "Factory adapters (U4/U5) are not yet wired to the real tools. "
        "The loop controller core is unit-tested against recorded verdicts; "
        f"routing for '{target}' resolved to the {decision.lane.value} lane."
    )


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


@demo_grp.command("record")
@click.argument("demo_id")
@click.option("--from", "run_id", type=int, required=True, help="Run-history id to snapshot.")
def demo_record_cmd(demo_id: str, run_id: int) -> None:
    """Snapshot a real run into a live_verified fixture + persisted report."""
    from . import __version__
    from .autonomous.report import render_report
    from .demos.registry import Registry
    from .demos.result import from_dict as result_from_dict
    from .memory.store import MemoryStore

    reg = Registry.load()
    if demo_id not in reg.manifests:
        raise click.ClickException(f"no demo with id {demo_id!r}.")
    store = MemoryStore.default()
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
    result_from_dict(payload)  # validate before writing
    results_dir = reg.demos_dir / "results"
    results_dir.mkdir(exist_ok=True)
    (results_dir / f"{demo_id}.json").write_text(json.dumps(payload, indent=2))
    (results_dir / f"{demo_id}.report.md").write_text(render_report(store, run_id))
    click.echo(f"Recorded {demo_id} from run #{run_id} ({payload['final_grade']}, {run.status}).")


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


if __name__ == "__main__":  # pragma: no cover
    main()
