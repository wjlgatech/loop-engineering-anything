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

SKILL_DIR = os.environ.get(
    "VLM_PROBE_SKILL_DIR",
    os.path.expanduser("~/Documents/Projects/FM-os/skills/vlm-failure-probe/reference"),
)
sys.path.insert(0, SKILL_DIR)

from probe_runner import MockVSS, PatchedVSS, gate, load_spec, run_probes, scorecard  # noqa: E402


def main(argv: list[str]) -> int:
    args = argv[1:]

    if args[:1] == ["probe"]:
        model = MockVSS() if "mock" in args else PatchedVSS()
        label = "mock" if "mock" in args else "patched"
        spec = load_spec()
        results = run_probes(model, spec)
        print(scorecard(f"vlm-probe ({label})", results, spec))
        ok, _ = gate(results, spec)
        return 0 if ok else 1

    print("usage: cli.py probe [--model mock|patched]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
