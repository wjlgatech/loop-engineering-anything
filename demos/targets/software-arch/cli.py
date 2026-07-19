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

import service


def main(argv: list[str]) -> int:
    args = argv[1:]
    want_json = "--json" in args

    if args[:1] == ["version"]:
        # BUG: crashes instead of emitting a clean version.
        raise TypeError("banner() takes 0 positional arguments but 1 was given")

    if args[:1] == ["health"]:
        # BUG: plain text, not JSON — an agent can't parse this.
        print("OK")
        return 0

    if args[:2] == ["items", "list"]:
        items = service.list_items()
        if not items:
            # BUG: non-JSON on the empty case, and no `items` key.
            print("no items")
            return 0
        print(items)
        return 0

    if args[:2] == ["items", "add"]:
        # BUG: prompts interactively — hangs / fails under no-TTY agent use.
        answer = input("confirm add? [y/N] ")
        if answer.strip().lower() != "y":
            print("aborted")
            return 1
        name = _flag(args, "--name") or "unnamed"
        qty = _flag(args, "--qty") or "1"
        item = service.create_item(name, qty)
        print(item)
        return 0

    print("usage: cli.py {version|health|items list|items add} [--json]")
    return 2


def _flag(args: list[str], flag: str) -> str | None:
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return None


if __name__ == "__main__":
    sys.exit(main(sys.argv))
