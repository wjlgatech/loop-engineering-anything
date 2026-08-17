#!/usr/bin/env python3
"""Audit a skill library against the @skills residency budget.

Applies the three-tier model from arXiv:2608.12610 (Yin et al., 12 Aug 2026) to a
real installed library. The paper's claim is that installation bundles three
separable things -- content, persistence, and auto-triggering -- and that only the
last one costs prompt residency, against a budget it bounds "conservatively at
fewer than a hundred reliable auto-trigger slots per agent."

This tool measures what a library actually spends, and names four failure classes
the paper predicts:

  PHANTOM     an entry whose SKILL.md cannot be read. It holds a name and loads
              nothing. The protocol is explicit that a conforming client "MUST
              refuse to :install it loudly rather than write a line that silently
              loads nothing" -- so silence here is a bug, not tidiness.
  DUPLICATE   one capability occupying more than one slot; the local form of the
              corpus-wide collision the paper measures (13,119 of 56,825 names).
  OVERLONG    a description past the protocol's "under ~120 chars" guidance. The
              description IS the trigger signal, so length is spent attention.
  UNTRIGGERED a skill with no description at all -- it cannot feed a trigger index.

It MEASURES and PROPOSES. It never mutates a library: --apply is deliberately not
implemented, because which skills deserve residency is the operator's judgement,
not a script's. The proposal is a ranked list to act on by hand.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

# The paper's conservative bound. It is ARGUED from the literature, not measured by
# the authors -- see trigger_reliability.py, which measures it here.
RELIABLE_SLOT_BOUND = 100
DESC_GUIDANCE_CHARS = 120


def scan(root: pathlib.Path) -> tuple[list[dict], list[dict]]:
    """Return (readable, phantom) skill records under root."""
    readable: list[dict] = []
    phantom: list[dict] = []
    for p in sorted(root.rglob("SKILL.md")):
        rel = str(p.relative_to(root))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            target = None
            try:
                target = str(p.readlink())
            except OSError:
                pass
            phantom.append({"path": rel, "dir": p.parent.name, "target": target, "why": type(e).__name__})
            continue
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        fm = m.group(1) if m else ""

        def field(key: str) -> str:
            mm = re.search(rf"^{key}:\s*(.*)$", fm, re.M)
            return mm.group(1).strip().strip("\"'") if mm else ""

        readable.append({
            "name": field("name") or p.parent.name,
            "desc": field("description"),
            "body_chars": len(text),
            "path": rel,
        })
    return readable, phantom


def audit(root: pathlib.Path) -> dict:
    readable, phantom = scan(root)

    by_name: dict[str, list[dict]] = collections.defaultdict(list)
    for r in readable:
        by_name[r["name"]].append(r)
    distinct = {n: v[0] for n, v in by_name.items()}
    duplicates = {n: [x["path"] for x in v] for n, v in by_name.items() if len(v) > 1}

    resident = sum(len(r["desc"]) for r in distinct.values())
    bodies = sum(r["body_chars"] for r in distinct.values())
    overlong = sorted(
        ((n, len(r["desc"])) for n, r in distinct.items() if len(r["desc"]) > DESC_GUIDANCE_CHARS),
        key=lambda kv: -kv[1],
    )
    untriggered = sorted(n for n, r in distinct.items() if not r["desc"])

    return {
        "root": str(root),
        "slot_bound_claimed_by_paper": RELIABLE_SLOT_BOUND,
        "skill_md_files": len(readable) + len(phantom),
        "readable": len(readable),
        "distinct_names": len(distinct),
        "over_budget_ratio": round(len(distinct) / RELIABLE_SLOT_BOUND, 2),
        "resident_index_chars": resident,
        "resident_index_tokens_est": resident // 4,
        "all_bodies_chars": bodies,
        "all_bodies_tokens_est": bodies // 4,
        "content_to_index_ratio": round(bodies / max(resident, 1), 1),
        "phantom": phantom,
        "duplicates": duplicates,
        "overlong": overlong,
        "untriggered": untriggered,
    }


def render(a: dict) -> str:
    L: list[str] = []
    add = L.append
    add("# Skill residency audit")
    add("")
    add(f"Library: `{a['root']}`")
    add("")
    add("## The budget")
    add("")
    add(f"- `SKILL.md` entries found: **{a['skill_md_files']}** "
        f"({a['readable']} readable, {len(a['phantom'])} phantom)")
    add(f"- Distinct skill names: **{a['distinct_names']}**")
    add(f"- Paper's conservative reliable-slot bound: **{a['slot_bound_claimed_by_paper']}**")
    add(f"- Over budget by: **{a['over_budget_ratio']}x**")
    add("")
    add(f"- Resident index (name + description): **{a['resident_index_chars']:,} chars** "
        f"(~{a['resident_index_tokens_est']:,} tokens)")
    add(f"- Every body, if all were resident: **{a['all_bodies_chars']:,} chars** "
        f"(~{a['all_bodies_tokens_est']:,} tokens)")
    add(f"- Content-to-index ratio: **{a['content_to_index_ratio']}x** — this is the "
        "paper's thesis as a single number: the index costs ~1/"
        f"{int(a['content_to_index_ratio'])} of the content.")
    add("")

    add("## PHANTOM — holds a name, loads nothing")
    add("")
    if not a["phantom"]:
        add("None. Every entry resolves.")
    else:
        add(f"**{len(a['phantom'])} entries.** The protocol says a client MUST refuse such an "
            "entry *loudly*. These fail silently instead: the capability is simply absent, and "
            "nothing tells you.")
        add("")
        for p in a["phantom"]:
            add(f"- `{p['dir']}` → `{p['target'] or '(unresolved)'}`")
    add("")

    add("## DUPLICATE — one capability, more than one slot")
    add("")
    if not a["duplicates"]:
        add("None.")
    else:
        add(f"**{len(a['duplicates'])} names installed more than once.** Each extra copy is a "
            "slot spent on a capability already present — the local form of the name collisions "
            "the paper measures across the public corpus.")
        add("")
        for n, paths in sorted(a["duplicates"].items())[:20]:
            add(f"- `{n}` ×{len(paths)}")
    add("")

    add(f"## OVERLONG — description past the protocol's ~{DESC_GUIDANCE_CHARS}-char guidance")
    add("")
    if not a["overlong"]:
        add("None.")
    else:
        add(f"**{len(a['overlong'])} of {a['distinct_names']}** exceed it. The description *is* "
            "the trigger signal, so every extra character is resident attention spent on one "
            "tenant of the index.")
        add("")
        for n, c in a["overlong"][:12]:
            add(f"- `{n}` — {c} chars ({c/DESC_GUIDANCE_CHARS:.1f}x guidance)")
    add("")

    add("## UNTRIGGERED — cannot feed a trigger index")
    add("")
    add("None." if not a["untriggered"] else ", ".join(f"`{n}`" for n in a["untriggered"]))
    add("")

    add("## Proposal")
    add("")
    over = a["distinct_names"] - a["slot_bound_claimed_by_paper"]
    add(f"To reach the argued bound, **{max(over, 0)} skills** must stop being resident. In "
        "@skills terms that is not deletion — it is demotion from tier 3 (auto-trigger) to "
        "tier 1 (addressed by path, read at the point of use). Ranked cheapest-first:")
    add("")
    add(f"1. Remove the **{len(a['phantom'])} phantom** entries. Zero capability lost — they "
        "already load nothing.")
    add(f"2. Collapse the **{len(a['duplicates'])} duplicated** names to one copy each.")
    add(f"3. Rewrite the **{len(a['overlong'])} overlong** descriptions toward "
        f"{DESC_GUIDANCE_CHARS} chars. Same coverage, less resident spend.")
    add("4. Demote every skill that is only ever invoked *by name* (a slash command you type) "
        "out of the auto-trigger index. If you always ask for it explicitly, it never needed a "
        "trigger slot — that is the paper's central point, and it is the largest available win.")
    add("")
    add("This tool does not apply any of the above. Which capabilities deserve residency is "
        "operator judgement, and a script that silently re-tiered a library would be making "
        "exactly the unreviewable change the protocol exists to prevent.")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", nargs="?", default=str(pathlib.Path.home() / ".claude"),
                    help="library root to scan (default: ~/.claude)")
    ap.add_argument("--json", action="store_true", help="emit the raw audit as JSON")
    ap.add_argument("--out", default=None, help="write the markdown report to this path")
    args = ap.parse_args()

    root = pathlib.Path(args.root).expanduser()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    a = audit(root)
    if args.json:
        print(json.dumps(a, indent=2))
        return 0
    report = render(a)
    if args.out:
        pathlib.Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
