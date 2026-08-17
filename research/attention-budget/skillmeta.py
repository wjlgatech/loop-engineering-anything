"""Read `SKILL.md` frontmatter correctly — including YAML block scalars.

WHY THIS MODULE EXISTS (bug found 2026-08-13)
---------------------------------------------
Both tools here originally parsed frontmatter with `^description:\\s*(.*)$`. That
regex is wrong for the block-scalar forms YAML permits, which real skills use:

    description: |
      A long description
      over several lines

    description: >-
      A folded description

The regex captured the INDICATOR (`|`, `>-`) and returned a one- or two-character
"description". It never raised; it just quietly produced a wrong value. That
understated the measured residency budget and, worse, fed meaningless probes into
the trigger-reliability experiment, whose ground truth then measured nothing but
this bug.

It is the same failure class the audit itself reports: a parser that returns a
plausible wrong answer instead of refusing. Hence one shared, tested reader.
"""

from __future__ import annotations

import pathlib
import re

_INDICATOR = re.compile(r"^[|>]([+-]?\d*|\d*[+-]?)$")


def parse_frontmatter(text: str) -> dict[str, str]:
    """Top-level scalar fields of a `---`-delimited YAML frontmatter block.

    Handles plain scalars, quoted scalars, and `|`/`>` block scalars (with any
    chomping/indent indicator). Nested mappings and sequences are skipped rather
    than guessed at — this is a frontmatter reader, not a YAML implementation.
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    if not m:
        return {}
    lines = m.group(1).split("\n")

    out: dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        km = re.match(r"^([A-Za-z0-9_-]+):[ \t]*(.*)$", line)
        if not km:
            i += 1
            continue
        key, rest = km.group(1), km.group(2).strip()

        if _INDICATOR.match(rest):
            # Block scalar: consume the indented continuation.
            block: list[str] = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and not re.match(r"^[ \t]", nxt):
                    break  # dedented to a new key
                block.append(nxt.strip())
                i += 1
            folded = " " if rest.startswith(">") else "\n"
            out[key] = folded.join(b for b in block if b != "").strip()
            continue

        if rest:
            out[key] = rest.strip("\"'")
        i += 1
    return out


def load_skills(root: pathlib.Path) -> tuple[list[dict], list[dict]]:
    """(readable, phantom) skill records under ``root``.

    A phantom is an entry whose `SKILL.md` cannot be read — it holds a name and
    loads nothing. It is reported, never silently skipped.
    """
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
            phantom.append({"path": rel, "dir": p.parent.name, "target": target,
                            "why": type(e).__name__})
            continue
        fm = parse_frontmatter(text)
        readable.append({
            "name": fm.get("name") or p.parent.name,
            "desc": fm.get("description", ""),
            "hint": fm.get("argument-hint", ""),
            "body_chars": len(text),
            "path": rel,
        })
    return readable, phantom


def distinct(readable: list[dict]) -> dict[str, dict]:
    """First record per skill name, in scan order."""
    out: dict[str, dict] = {}
    for r in readable:
        out.setdefault(r["name"], r)
    return out
