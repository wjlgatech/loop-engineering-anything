#!/usr/bin/env python3
"""software-arch — "make a local microservice agent-native" proof target.

This is the deliberately-buggy *baseline* ("before"). It is meant to be a
non-interactive, JSON-emitting ops CLI over the ``service`` module (the local
microservice), but it fails the cli-judge ``software-arch`` suite:

  - ``version --json``           must exit 0 without crashing        (BUG: raises TypeError)
  - ``health --json``            must emit JSON with a ``status`` = ok (BUG: prints plain text)
  - ``items list --json``        must emit JSON with an ``items`` key  (BUG: prints "no items")
  - ``items add --name .. --json`` must run one-shot, no prompt        (BUG: prompts for confirm)

The loop's job is to refactor THIS file until the referee grades it A. The
committed copy stays the baseline so the before/after is reproducible; a run
mutates a workspace copy.
"""
from __future__ import annotations

import sys
import json # Import json module

import service


def main(argv: list[str]) -> int:
    args = argv[1:]
    want_json = "--json" in args

    # Remove --json from args so it doesn't interfere with other flag parsing
    if want_json:
        args = [arg for arg in args if arg != "--json"]

    if args[:1] == ["version"]:
        # FIX: Emit JSON with the version and do not crash.
        if want_json:
            print(json.dumps({"version": service.VERSION}))
        else:
            print(service.VERSION) # Keep plain text for non-JSON
        return 0

    if args[:1] == ["health"]:
        # FIX: Emit JSON with status.
        health_info = service.health()
        if want_json:
            print(json.dumps(health_info))
        else:
            print(health_info["status"]) # Keep plain text for non-JSON
        return 0

    if args[:2] == ["items", "list"]:
        items = service.list_items()
        # FIX: Always emit JSON with an `items` key, even if empty.
        if want_json:
            print(json.dumps({"items": items}))
        else:
            if not items:
                print("no items") # Keep original plain text behavior
            else:
                # For plain text, let's just show count.
                print(f"{len(items)} items")
        return 0

    if args[:2] == ["items", "add"]:
        # FIX: Remove interactive prompt.
        # FIX: Ensure qty is int and handle missing/invalid args gracefully.
        name = _flag(args, "--name")
        if name is None:
            if want_json:
                print(json.dumps({"error": "missing --name argument"}), file=sys.stderr)
            else:
                print("Error: missing --name argument", file=sys.stderr)
            return 1

        qty_str = _flag(args, "--qty")
        try:
            qty = int(qty_str) if qty_str else 1
        except ValueError:
            if want_json:
                print(json.dumps({"error": "invalid value for --qty"}), file=sys.stderr)
            else:
                print("Error: invalid value for --qty", file=sys.stderr)
            return 1

        item = service.create_item(name, qty)
        if want_json:
            print(json.dumps(item))
        else:
            print(f"Added item: {item['name']} (ID: {item['id']}, Qty: {item['qty']})") # More informative plain text
        return 0

    print("usage: cli.py {version|health|items list|items add} [--json]")
    return 2


def _flag(args: list[str], flag: str) -> str | None:
    """Extracts the value for a given flag from the argument list."""
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return None


if __name__ == "__main__":
    sys.exit(main(sys.argv))
