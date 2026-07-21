#!/usr/bin/env python3
"""Onboarding helper for harnessx: print the repo's key components from its KG summary.

Deterministic, no network, no LLM. Run before touching the repo so an agent acts
on a map, not a guess.
"""
from __future__ import annotations

import json
import os


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    summary_path = os.path.join(here, os.pardir, "kg-summary.json")
    if not os.path.isfile(summary_path):
        print("kg-summary.json not found next to the skill")
        return 1
    s = json.load(open(summary_path, encoding="utf-8"))
    print(f"repo: {s.get('repo')}")
    print(f"nodes: {s.get('nodes')}  edges: {s.get('edges')}")
    et = s.get("edge_types") or {}
    if et:
        print("relations: " + ", ".join(f"{k}={v}" for k, v in list(et.items())[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
