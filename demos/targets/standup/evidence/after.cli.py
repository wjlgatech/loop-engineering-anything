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

    if args and args[0] == "version":
        # Fix: handle version command to exit cleanly and optionally output JSON.
        if "--json" in args:
            print(json.dumps({"version": "1.0.0"}))
        else:
            print("standup CLI version 1.0.0")
        return 0

    if args[:2] == ["standup", "digest"]:
        # Fix: implement structured JSON digest for `standup digest --json`.
        if "--json" in args:
            data = json.loads(ACTIVITY.read_text())
            yesterday = []
            today = []
            blockers = []

            for event in data["events"]:
                if not isinstance(event, dict) or "type" not in event or "msg" not in event:
                    continue # Skip malformed or incomplete events

                event_type = event["type"]
                event_msg = event["msg"]

                if event_type in ["commit", "pr", "review"]:
                    yesterday.append(event_msg)
                elif event_type == "plan":
                    today.append(event_msg)
                elif event_type == "note" and "blocked on" in event_msg.lower():
                    blockers.append(event_msg)

            digest = {
                "yesterday": yesterday,
                "today": today,
                "blockers": blockers,
            }
            print(json.dumps(digest, indent=2)) # Use indent for readability
            return 0
        else:
            # Original behavior for `standup digest` without --json.
            # This path is not explicitly failing according to the prompt, so keep it.
            data = json.loads(ACTIVITY.read_text())
            for event in data["events"]:
                if isinstance(event, dict) and "msg" in event:
                    print(event["msg"])
            return 0

    print("unknown command", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
