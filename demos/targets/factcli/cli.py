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


def main(argv: list[str]) -> int:
    args = argv[1:]

    if args[:1] == ["version"]:
        # BUG: crashes instead of emitting a clean version — Traceback on a
        # non-zero exit fails the banner-signature contract.
        raise RuntimeError("version handler not implemented")

    if args[:2] == ["project", "new"]:
        # BUG: prompts for input (blocks / EOFErrors under no-TTY) and prints
        # plain text, not JSON — fails the non-interactive contract.
        name = input("project name? ")
        print("created project " + name)
        return 0

    if args[:2] == ["fs", "ls"]:
        # BUG: prints a bare array with no ``items`` key — fails the
        # empty-result-is-valid-JSON contract.
        print("[]")
        return 0

    print("unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
