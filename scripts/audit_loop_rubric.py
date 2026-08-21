#!/usr/bin/env python3
"""Score this engine against the Agent Loop Engineering rubric — with observed evidence.

The rubric (docs/rubrics/agent-loop-engineering.yml) encodes the claims of a webinar
summary that asserts what a mature agent loop must have and verifies none of it against a
running system. This script is the missing half: every claim becomes a probe against
shipped code or a real test run, and the score is whatever the probes return.

Discipline (the operationalizing-a-rubric playbook, which ships with the anyagent
skill rather than in this repo -- summarised here so this file stands alone):

  * Evidence is OBSERVED -- a symbol at a file:line, or a pytest node that actually
    passes. Never a claim in prose.
  * No evidence => NO.
  * A probe that cannot run is `unmeasured`: excluded from the rate AND blocking. An
    unmeasured item is never a silent pass, because "I could not look" is not "it works".
  * `expect: absent` items are honest gap declarations. They PASS while the gap is real
    and FAIL the moment the gap silently closes, so the published gap list cannot rot.
  * Exits non-zero under --gate, so CI can hold the line.

Usage:
    python3 scripts/audit_loop_rubric.py [--json] [--gate] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUBRIC = ROOT / "docs" / "rubrics" / "agent-loop-engineering.yml"

PASS, FAIL, UNMEASURED = "pass", "fail", "unmeasured"


def _iter_files(paths: list[str]) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for rel in paths:
        p = ROOT / rel
        if p.is_dir():
            out.extend(sorted(q for q in p.rglob("*.py") if "__pycache__" not in q.parts))
        elif p.is_file():
            out.append(p)
    return out


def probe_grep(spec: dict) -> tuple[bool, str]:
    """Observed evidence: the first file:line where the pattern appears."""
    files = _iter_files(spec.get("paths", []))
    if not files:
        raise FileNotFoundError(f"no such path(s): {spec.get('paths')}")
    rx = re.compile(spec["pattern"])
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if rx.search(line):
                return True, f"{f.relative_to(ROOT)}:{n}"
    return False, f"pattern /{spec['pattern']}/ not found in {len(files)} file(s)"


def probe_pytest(spec: dict) -> tuple[bool, str]:
    """Observed evidence: the test is RUN, not merely present on disk."""
    node = spec["node"]
    target = ROOT / node.split("::")[0]
    if not target.exists():
        raise FileNotFoundError(f"no such test file: {node}")
    py = ROOT / ".venv" / "bin" / "python"
    exe = [str(py)] if py.exists() else [sys.executable]
    r = subprocess.run(exe + ["-m", "pytest", node, "-q", "--no-header", "-x"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    tail = (r.stdout.strip().splitlines() or ["(no output)"])[-1][:110]
    return r.returncode == 0, f"{node} -> {tail}"


PROBES = {"grep": probe_grep, "pytest": probe_pytest}


def run_item(item: dict) -> dict:
    spec = item["probe"]
    expect_absent = item.get("expect") == "absent"
    fn = PROBES.get(spec.get("type"))
    if fn is None:
        return {**item, "status": UNMEASURED, "evidence": f"unknown probe type {spec.get('type')!r}"}
    try:
        found, evidence = fn(spec)
    except Exception as e:  # noqa: BLE001 -- a probe that cannot run is unmeasured, never a pass
        return {**item, "status": UNMEASURED, "evidence": f"probe could not run: {e}"}
    if expect_absent:
        ok = not found
        evidence = ("gap confirmed absent" if ok
                    else f"GAP CLOSED without updating the rubric: {evidence}")
    else:
        ok = found
    return {**item, "status": PASS if ok else FAIL, "evidence": evidence}


def audit(rubric: pathlib.Path | None = None) -> dict:
    path = rubric or RUBRIC
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    results = [run_item(i) for i in doc["items"]]

    verifiable = [r for r in results if not r.get("expect")]
    implemented = [r for r in verifiable if r["status"] == PASS]
    missing = [r for r in verifiable if r["status"] == FAIL]
    gaps = [r for r in results if r.get("expect") == "absent"]
    unmeasured = [r for r in results if r["status"] == UNMEASURED]

    scored = [r for r in verifiable if r["status"] != UNMEASURED]
    rate = len([r for r in scored if r["status"] == PASS]) / len(scored) if scored else 0.0
    gate_ok = not missing and not unmeasured and all(g["status"] == PASS for g in gaps)

    return {
        "rubric": str(path.relative_to(ROOT)),
        "provenance": doc.get("provenance"),
        "source": doc["source"],
        "total_items": len(results),
        "verifiable": len(verifiable),
        "implemented": len(implemented),
        "missing": len(missing),
        "declared_gaps": len(gaps),
        "unmeasured": len(unmeasured),
        "conformance_rate": round(rate, 3),
        "gate_ok": gate_ok,
        "results": results,
    }


def render(a: dict) -> str:
    src = a["source"]
    L = ["# Agent Loop Engineering — conformance audit", ""]
    if a.get("provenance"):
        # A generated file gets read on its own, far from the rubric header. If the rubric
        # declares itself a reconstruction, its output says so on line 3 or the number
        # travels without its caveat -- which is the defect this whole audit is about.
        L += [f"> **{a['provenance'].strip()}**", ""]
    L += [
         f"Rubric: `{a['rubric']}` — {a['total_items']} items drawn from "
         f"*{src['title']}* ({src['publisher']}, received {src['received']}).", "",
         f"That source is a **{src['nature']}**. Every claim below is scored against shipped "
         "code or a test that was actually executed. No evidence means no.", "",
         f"**Conformance: {a['implemented']}/{a['verifiable']} "
         f"({a['conformance_rate']*100:.0f}%)** verifiable claims implemented · "
         f"{a['declared_gaps']} declared gaps · {a['unmeasured']} unmeasured · "
         f"gate **{'PASS' if a['gate_ok'] else 'FAIL'}**", ""]

    for bucket, title in ((PASS, "Implemented — with observed evidence"),
                          (FAIL, "NOT implemented"),
                          (UNMEASURED, "Unmeasured — blocks the gate, never counts as a pass")):
        rows = [r for r in a["results"] if r["status"] == bucket and not r.get("expect")]
        if not rows:
            continue
        L += [f"## {title}", ""]
        for r in rows:
            L.append(f"- **{r['id']}** · {r['section']}")
            L.append(f"  - claim: {r['claim']}")
            L.append(f"  - evidence: `{r['evidence']}`")
            if r.get("rationale"):
                L.append(f"  - why it is still a miss: {r['rationale'].strip()}")
        L.append("")

    gaps = [r for r in a["results"] if r.get("expect") == "absent"]
    if gaps:
        L += ["## Declared gaps — the engine does NOT do these, and says so", "",
              "Each probe passes while the gap is real and fails the moment it silently closes, "
              "so this list cannot quietly go stale.", ""]
        for r in gaps:
            mark = "confirmed absent" if r["status"] == PASS else "STALE — gap closed, update the rubric"
            L.append(f"- **{r['id']}** · {r['section']}")
            L.append(f"  - claim: {r['claim']}")
            L.append(f"  - status: **{mark}** — {r.get('gap_note', '')}")
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rubric", default=None,
                    help="score an alternative rubric file (e.g. an archived version)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", action="store_true", help="exit 1 unless every item passes")
    ap.add_argument("--out")
    args = ap.parse_args()

    a = audit(pathlib.Path(args.rubric).resolve() if args.rubric else None)
    text = json.dumps(a, indent=2) if args.json else render(a)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    if args.gate and not a["gate_ok"]:
        print(f"\nGATE FAIL: {a['missing']} missing, {a['unmeasured']} unmeasured", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
