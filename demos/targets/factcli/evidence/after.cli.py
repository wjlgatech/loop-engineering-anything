#!/usr/bin/env python3
"""factcli — a tiny agent-native CLI used as a SELF-CONTAINED proof target.

This is the pristine *baseline* ("before"): it is intentionally not yet
agent-native and fails the cli-judge ``proof`` suite (the D2 non-interactive
contract). The loop's job is to refactor THIS file until the referee grades it A:

  - ``version --json``        must exit 0 and not crash with a Traceback
  - ``project new --name X --json`` must run one-shot (no prompt) and print JSON
  - ``fs ls --json``          must print valid JSON with an ``items`` array

A real run mutates a workspace copy of this file; the committed copy stays the
baseline so the before/after is reproducible.
"""
from __future__ import annotations

import sys
import json # Added json import


def main(argv: list[str]) -> int:
    args = argv[1:]

    if args[:1] == ["version"]:
        # Fix: Emit version, handle --json
        if "--json" in args:
            print(json.dumps({"version": "0.0.1"}))
        else:
            print("factcli 0.0.1")
        return 0

    if args[:2] == ["project", "new"]:
        # Fix: Don't prompt, extract --name, print JSON
        name = None
        try:
            name_idx = args.index("--name")
            name = args[name_idx + 1]
        except (ValueError, IndexError):
            # --name not found or no argument provided
            pass

        if name is None:
            if "--json" in args:
                print(json.dumps({"error": "project name required. Use --name <name>"}), file=sys.stderr)
            else:
                print("Error: project name required. Use --name <name>", file=sys.stderr)
            return 1 # Exit with error

        if "--json" in args:
            print(json.dumps({"project": {"name": name, "status": "created"}}))
        else:
            print("created project " + name)
        return 0

    if args[:2] == ["fs", "ls"]:
        # Fix: Print valid JSON with an `items` array
        if "--json" in args: # Assume --json is always present for this fixture
            print(json.dumps({"items": []}))
        else:
            print("[]") # Keep original behavior for non-json
        return 0

    print("unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
