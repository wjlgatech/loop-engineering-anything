"""ToolingSkillFactory — generate agentic tooling from a repo's knowledge graph (U4).

The tooling half's generator: given a cited repo's knowledge graph (the U2
artifact, ``kg-summary.json``), it emits a **skill** — a ``SKILL.md`` plus a real,
compiling helper (``scripts/kg_query.py``) — that makes the repo agent-native
(an agent can run the helper to learn the repo's key components before touching
it). Paired with the U3 ``ToolingJudge`` as referee, this closes the loop:
generate → grade → (refine) → converge.

**Deterministic, no LLM** (matches the KG builder's ethos): cheap, reproducible,
and faithful by construction — the skill's ``name`` matches its directory, every
referenced file is one it actually ships, and the helper compiles. So the
artifact grades ``A`` on the U3 judge's structure/fidelity/safety axes without
any post-hoc fixing. A KG-keyed *generator* is the net-new piece; the referee
(U3) and the KG (U2) already exist.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from .base import GenerateResult

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG.sub("-", str(text).strip().lower()).strip("-") or "repo"


def _load_kg_summary(target: str) -> tuple[dict, str | None]:
    """Resolve ``target`` to a KG summary dict + the summary file path (or None).

    Accepts a path to a ``kg-summary.json``, or a directory containing one. When
    neither resolves, returns a minimal summary derived from the target label so
    generation still produces an honest (if thinner) skill rather than failing.
    """
    t = str(target).strip()
    cand = t if (os.path.isfile(t) and t.endswith(".json")) else os.path.join(t, "kg-summary.json")
    if os.path.isfile(cand):
        try:
            return json.load(open(cand, encoding="utf-8")), cand
        except (OSError, json.JSONDecodeError):
            pass
    return {"repo": os.path.basename(t.rstrip("/")) or t}, None


def _top_hubs(summary: dict, n: int = 8) -> list[str]:
    # kg-summary from build_repo_kg carries node/edge histograms; the hub list is
    # optional. Fall back to the edge-type keys as "what this codebase does".
    hubs = summary.get("top_hubs") or []
    if hubs:
        return [str(h) for h in hubs[:n]]
    return list((summary.get("edge_types") or {}).keys())[:n]


_HELPER = '''#!/usr/bin/env python3
"""Onboarding helper for {repo}: print the repo's key components from its KG summary.

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
    print(f"repo: {{s.get('repo')}}")
    print(f"nodes: {{s.get('nodes')}}  edges: {{s.get('edges')}}")
    et = s.get("edge_types") or {{}}
    if et:
        print("relations: " + ", ".join(f"{{k}}={{v}}" for k, v in list(et.items())[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _skill_md(name: str, repo: str, goal: str, summary: dict, hubs: list[str]) -> str:
    import yaml

    nodes = summary.get("nodes")
    edges = summary.get("edges")
    scale = f" ({nodes} nodes / {edges} edges)" if nodes and edges else ""
    hub_lines = "\n".join(f"- `{h}`" for h in hubs) or "- (no component data in the KG summary)"
    desc = (
        f"Make {repo} agent-native — onboard an agent to {repo}'s structure and key "
        f"components from its knowledge graph before it touches the code."
    )
    # Build frontmatter via yaml.safe_dump so a value with a colon/quote is always
    # valid YAML (a hand-formatted 'description: ...:...' would break the parser).
    fm = yaml.safe_dump({"name": name, "description": desc}, sort_keys=False, allow_unicode=True).strip()
    return f"""---
{fm}
---

# {name}

Agent-native onboarding for **{repo}**{scale}, generated from its knowledge graph.
Goal: {goal or "make this repo agent-native"}.

## Key components (from the KG)

{hub_lines}

## Use

Run the onboarding helper first — it prints the repo's components from the bundled
KG summary (deterministic, no network):

```
python scripts/kg_query.py
```

Then read the named components above before making changes. This skill ships its
own `kg-summary.json`, so the helper works offline.
"""


@dataclass
class ToolingSkillFactory:
    """Implements the ``Factory`` protocol for the tooling (skill) domain."""

    def generate(self, target: str, goal: str = "", workdir: str = ".") -> GenerateResult:
        summary, summary_path = _load_kg_summary(target)
        repo = str(summary.get("repo") or os.path.basename(str(target).rstrip("/")) or "repo")
        name = f"use-{_slug(repo)}"
        skill_dir = os.path.join(workdir, name)
        os.makedirs(os.path.join(skill_dir, "scripts"), exist_ok=True)

        hubs = _top_hubs(summary)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(_skill_md(name, repo, goal, summary, hubs))
        with open(os.path.join(skill_dir, "scripts", "kg_query.py"), "w", encoding="utf-8") as f:
            f.write(_HELPER.format(repo=repo))
        # Ship the KG summary alongside so the helper is self-contained + faithful.
        with open(os.path.join(skill_dir, "kg-summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        manifest = {
            "id": name,
            "kind": "skill",
            "source_repo": repo,
            "kg_nodes": summary.get("nodes"),
            "kg_summary_source": summary_path,
        }
        return GenerateResult(
            tool_path=skill_dir,
            lane="tooling",
            ok=True,
            manifest=manifest,
            logs=f"generated skill {name!r} for {repo} from {'KG summary' if summary_path else 'label only'}",
        )
