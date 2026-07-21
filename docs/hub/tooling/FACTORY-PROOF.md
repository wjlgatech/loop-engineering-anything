# ToolingSkillFactory — generate→grade→converge proof (U4)

U3 gave the factory a *referee* for tooling; U4 gives it a *generator*. Together
they close the tooling half of the loop: point the factory at a cited repo's
knowledge graph and it emits a skill that the independent U3 judge grades — no
post-hoc fixing, deterministically (no LLM).

## End-to-end run (real HarnessX KG, 2026-07-21)

Input: the committed `docs/hub/kg/harnessx/kg-summary.json` (the U2 artifact —
6317 nodes / 21715 edges). Driver: `scripts/build_repo_tooling.py`.

```
generated: use-harnessx  (from the KG summary)
grade:     A   score: 100.0   safe: True        # ToolingJudge (U3), independent referee
controller: CONVERGED  grade=A  iterations=1     # real LoopController, generate→grade→converge
RESULT: PASS (generate→grade→converge)
```

The generated skill (`docs/hub/tooling/use-harnessx/`) is faithful by
construction, which is exactly why it grades A:

- **structure** — valid YAML frontmatter (`name: use-harnessx`, a real description).
- **fidelity** — `name` matches the directory; it references `scripts/kg_query.py`,
  which it actually ships and which **compiles and runs** (prints the repo's
  components from the bundled `kg-summary.json` — a genuine onboarding helper, not a
  stub); it bundles its own KG summary so the helper works offline.
- **safety** — no unsafe command or secret.

## What it generates

For a repo with a knowledge graph, per invocation:

- `SKILL.md` — frontmatter (safe YAML via `safe_dump`) + a body naming the repo's
  key components (the KG's top hubs) and how to onboard.
- `scripts/kg_query.py` — a deterministic, no-network helper that prints the repo's
  components from the bundled summary.
- `kg-summary.json` — shipped alongside so the skill is self-contained.

Without a KG it degrades honestly (a thinner but still loadable, safe, faithful
skill), never fabricating structure.

## Why this composes

The factory (`ToolingSkillFactory`) and referee (`ToolingJudge`) are **distinct
objects** — maker ≠ checker holds — so the A grade is the referee's verdict, not
the generator grading its own work. The `tooling-skill` domain now binds both, so
the loop generates → grades → converges tooling end to end. Reproduce:
`pytest tests/test_tooling_factory.py` and `python scripts/build_repo_tooling.py`.

## What remains

This generates a **skill** (SKILL.md + helper). Emitting a **plugin** (agents +
hooks) or an **MCP server** keyed off the KG is the natural follow-on — the same
Factory seam, a richer template. And the free-tier LLM refiner can now lift a
sub-A generated skill toward A (the refine path), since the U3 judge gives it
dimension-level fixtures to act on.
