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
import json # Added json import

SKILL_DIR = os.environ.get(
    "VLM_PROBE_SKILL_DIR",
    os.path.expanduser("~/Documents/Projects/FM-os/skills/vlm-failure-probe/reference"),
)
sys.path.insert(0, SKILL_DIR)

from probe_runner import MockVSS, PatchedVSS, gate, load_spec, run_probes, scorecard  # noqa: E402


def main(argv: list[str]) -> int:
    args = argv[1:]

    # Parse common flags: --model <type> and --json
    model_type = "patched"
    json_output = False
    remaining_args = []

    i = 0
    while i < len(args):
        if args[i] == "--model":
            if i + 1 < len(args):
                model_type = args[i+1]
                i += 1 # Skip model type
            else:
                print("Error: --model requires an argument (mock|patched)", file=sys.stderr)
                return 2
        elif args[i] == "--json":
            json_output = True
        else:
            remaining_args.append(args[i])
        i += 1

    if not remaining_args:
        print("usage: cli.py <version|probe> ...", file=sys.stderr)
        return 2

    command = remaining_args[0]
    # command_args are not used directly as flags are already parsed out

    if command == "version":
        if json_output:
            print(json.dumps({"version": "1.0.0"})) # Hardcoding version for simplicity
        else:
            print("vlm-probe version 1.0.0")
        return 0

    elif command == "probe":
        if len(remaining_args) < 2:
            print("usage: cli.py probe <run|gate> [--model mock|patched] [--json]", file=sys.stderr)
            return 2

        subcommand = remaining_args[1]

        # Determine the model instance based on parsed model_type
        model = MockVSS() if model_type == "mock" else PatchedVSS()
        spec = load_spec()
        results = run_probes(model, spec)

        if subcommand == "run":
            if json_output:
                # The 'modes' map requirement: run_probes returns {mode_id: {...}}
                print(json.dumps({"modes": results}))
            else:
                # Human-readable scorecard for non-json output
                print(scorecard(f"vlm-probe ({model_type})", results, spec))
            return 0 # 'run' is report-only, always exits 0

        elif subcommand == "gate":
            ok, reasons = gate(results, spec)
            if json_output:
                print(json.dumps({"gate_pass": ok, "reasons": reasons}))
            # For 'gate', if not --json, it should just exit with status code, no stdout.
            return 0 if ok else 1

        else:
            print(f"Error: Unknown probe subcommand '{subcommand}'", file=sys.stderr)
            return 2

    else:
        print(f"Error: Unknown command '{command}'", file=sys.stderr)
        print("usage: cli.py <version|probe> ...", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
