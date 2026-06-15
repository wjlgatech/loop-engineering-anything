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


if __name__ == "__main__":  # pragma: no cover
    main()
