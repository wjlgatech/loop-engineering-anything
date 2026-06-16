#!/usr/bin/env python3
"""standup — automate-your-own-job-first proof target: a daily standup digest CLI.

This is the buggy *baseline* ("before"). A team-lead used to hand-turn the raw
activity in ``activity.json`` (the captured task payload) into a structured
standup digest. This CLI is supposed to do that for them — but it doesn't yet,
and fails the cli-judge ``automate-your-job`` suite:

  - ``version --json``        must exit 0 without crashing
  - ``standup digest --json`` must emit ONE JSON object with ``yesterday`` /
    ``today`` / ``blockers`` arrays derived from the captured activity (a
    ``blocked on …`` note must surface under ``blockers``)

The loop's job is to refactor THIS file until the referee grades it A. The
committed copy stays the baseline so the before/after is reproducible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ACTIVITY = Path(__file__).parent / "activity.json"


def main(argv: list[str]) -> int:
    args = argv[1:]

    if args[:1] == ["version"]:
        # BUG: crashes instead of emitting a clean version.
        raise RuntimeError("version handler not implemented")

    if args[:2] == ["standup", "digest"]:
        # BUG: dumps each event message as a plain-text line — not the structured
        # yesterday/today/blockers JSON digest the lead actually produced.
        data = json.loads(ACTIVITY.read_text())
        for event in data["events"]:
            if isinstance(event, dict) and "msg" in event:
                print(event["msg"])
        return 0

    print("unknown command")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
