#!/usr/bin/env python3
"""vlm-probe — a NAIVE wrap of FM-os `vlm-failure-probe` used as a proof target.

This is the pristine *baseline* ("before"): a faithful first-pass wrap of the
FM-os probe engine (github.com/wjlgatech/FM-os, skills/vlm-failure-probe) of
the kind a human dashes off — it prints the human-readable scorecard, has no
``version`` command, and ignores ``--json`` entirely. Nothing is planted: it
fails the cli-judge ``vlm-probe`` agent-native contract simply because it was
written for a human, not an agent. The loop's job is to refactor THIS file
until the referee grades it A:

  - ``version --json``                        exit 0, no Traceback, no prompt
  - ``probe run --model mock --json``         one-shot, valid JSON with a ``modes`` map
  - ``probe gate --model mock --json``        exit 1 (an honest gate FAILS the failing model)
  - ``probe gate --model patched --json``     exit 0, JSON with ``gate_pass``, no log noise

The underlying engine is resolved from ``VLM_PROBE_SKILL_DIR`` (the FM-os
skill's ``reference/`` dir). A real run mutates a workspace copy of this file;
the committed copy stays the baseline so the before/after is reproducible.
"""
from __future__ import annotations

import os
import sys
import argparse
import json

__version__ = "1.0.0"

SKILL_DIR = os.environ.get(
    "VLM_PROBE_SKILL_DIR",
    os.path.expanduser("~/Documents/Projects/FM-os/skills/vlm-failure-probe/reference"),
)
sys.path.insert(0, SKILL_DIR)

from probe_runner import MockVSS, PatchedVSS, gate, load_spec, run_probes, scorecard  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="vlm-probe CLI for agent interaction.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  cli.py version --json
  cli.py probe run --model mock --json
  cli.py probe gate --model patched --json
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show program's version number.",
        description="Show program's version number."
    )
    version_parser.add_argument("--json", action="store_true", help="Output version in JSON format.")
    version_parser.set_defaults(func=handle_version)

    # Probe command
    probe_parser = subparsers.add_parser(
        "probe",
        help="Run VLM probes.",
        description="Run VLM probes with various subcommands."
    )
    probe_subparsers = probe_parser.add_subparsers(dest="probe_command", help="Probe subcommands", required=True)

    # Probe run command
    probe_run_parser = probe_subparsers.add_parser(
        "run",
        help="Run VLM probes and report scorecard.",
        description="Run VLM probes and report a scorecard of results."
    )
    probe_run_parser.add_argument(
        "--model",
        choices=["mock", "patched"],
        default="mock",
        help="Specify the VLM model to use (mock or patched)."
    )
    probe_run_parser.add_argument("--json", action="store_true", help="Output results in JSON format.")
    probe_run_parser.set_defaults(func=handle_probe_run)

    # Probe gate command
    probe_gate_parser = probe_subparsers.add_parser(
        "gate",
        help="Run VLM probes and check gate condition.",
        description="Run VLM probes and check if the gate condition passes."
    )
    probe_gate_parser.add_argument(
        "--model",
        choices=["mock", "patched"],
        default="mock",
        help="Specify the VLM model to use (mock or patched)."
    )
    probe_gate_parser.add_argument("--json", action="store_true", help="Output results in JSON format.")
    probe_gate_parser.set_defaults(func=handle_probe_gate)

    args = parser.parse_args(argv[1:])

    # Call the handler function associated with the subcommand
    return args.func(args)


def handle_version(args) -> int:
    if args.json:
        print(json.dumps({"version": __version__}))
    else:
        print(f"vlm-probe {__version__}")
    return 0

def handle_probe_run(args) -> int:
    model_instance = MockVSS() if args.model == "mock" else PatchedVSS()
    label = args.model

    spec = load_spec()
    results = run_probes(model_instance, spec)

    if args.json:
        # run_probes returns {mode_id: {"measured", "score", "threshold", "probes"}}
        modes_data = {
            mode_id: {
                "measured": r["measured"],
                "score": r["score"],
                "threshold": r["threshold"],
            }
            for mode_id, r in results.items()
        }
        ok, reasons = gate(results, spec)
        output_json = {"modes": modes_data, "gate_pass": ok, "reasons": reasons}
        print(json.dumps(output_json))
    else:
        print(scorecard(f"vlm-probe ({label})", results, spec))
    return 0

def handle_probe_gate(args) -> int:
    model_instance = MockVSS() if args.model == "mock" else PatchedVSS()
    label = args.model

    spec = load_spec()
    results = run_probes(model_instance, spec)
    ok, _ = gate(results, spec)

    if args.json:
        print(json.dumps({"gate_pass": ok}))
    else:
        print(scorecard(f"vlm-probe ({label})", results, spec))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
