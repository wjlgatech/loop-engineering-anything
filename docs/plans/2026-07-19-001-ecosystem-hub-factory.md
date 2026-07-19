---
id: 2026-07-19-001
title: ecosystem-hub factory — cited repo → {knowledge graph, agentic tooling}
status: draft
---

# The ecosystem hub: turn every top-rated cited repo into knowledge + tooling

## The vision (why a hub)

`loop-engineering-anything` is positioned as the **hub of three things**:

1. **Knowledge** — what each cited repo *is* (a knowledge graph).
2. **Tooling** — what each cited repo lets you *do* (grade-gated skills / plugins / MCP servers / workflows).
3. **Experts** — *who* built each (authors ↔ repos ↔ tools, cross-linked).

The factory ingests each **top-rated cited repo** and emits, per repo, a knowledge
graph **and** agentic tooling — every artifact graded by an independent referee
before it ships. The hub is then a **graph-of-graphs**: the union of per-repo KGs,
cross-linked by expert and by tool, queryable over MCP.

The ingestion queue is data, not code: **`docs/cited-repos.yaml`** (8 T1/T2
targets, SHA-pinned, license-gated). This plan is the *how*.

## The unit pipeline (compose, don't reinvent)

For one repo, the factory is a five-stage pipeline built almost entirely from
blocks that already exist:

| Stage | Block (exists today) | Output |
|---|---|---|
| 1. Fetch + pin | `git clone` at the registry SHA | a frozen checkout |
| 2. Knowledge graph | **understand-anything** `/understand` (13 node / 26 edge types, HTML dashboard, git-hook auto-refresh) — or **graphify** when the repo drags in papers/docs (community clustering, `--mcp`) | `knowledge-graph.json` + dashboard |
| 3. Tooling seed | **`cli-anything build`** (already loopeng's codebase `Factory`) → a Click CLI **+ SKILL.md** v0 | runnable tooling v0 |
| 4. Grade + converge | **loop-engineering-anything** controller — `Factory`/`Judge`/`Domain` seams, maker≠checker integrity, budget guards, checkpoint-rollback, exportable learnings | Grade-A tooling (or honest STOP) |
| 5. Package + publish | **SKILL.md in a public git repo** (npx-skills-installable) + KG over **MCP** (`graphify --mcp`) | portable, cross-harness capability |

Only two things are genuinely new (see **The gap** below); everything else is
wiring existing parts.

## The five axes — each as a concrete mechanism, not an adjective

### High quality — the grader is the product
The whole repo already bets on this (see `docs/solutions/integrate-loop-engineering.md`):
three centuries of feedback loops show **every dead improvement loop died at the
grading step, not generation.** So:
- **Grade both artifacts, independently.** Tooling → the loop controller's
  `CLI-Judge` referee (maker≠checker enforced by `loop/integrity.py`); KG →
  understand-anything's `graph-reviewer` + graphify's per-edge
  `EXTRACTED/INFERRED/AMBIGUOUS` audit tags.
- **Grade-gate distribution.** Nothing publishes below the bar — a `BLOCKED_SAFETY`
  or sub-A tool STOPS honestly (as `software-arch` and `biotech-discovery` already
  demonstrate) rather than shipping a fabricated green.
- **Give the grader requisite variety** (Ashby): the tooling-Judge must be able to
  distinguish as many failure modes as the generator can produce, or it gets gamed.

### Fast — parallel + incremental
- **Fleet the repos** — `loop-anything fleet` already runs targets in topological
  waves over per-item git worktrees; the 8 T1/T2 repos ingest concurrently.
- **Incremental, not from-scratch** — understand-anything and graphify both cache
  per-file and re-process only `git diff`-changed files; a re-ingest of an unchanged
  repo is near-free.
- **Deterministic phases are free** — tree-sitter/AST extraction (both KG tools)
  and graphify's code-only fast path skip the LLM entirely.

### Cheap — free-tier LLM + tiered depth
- **Free-tier refiner chain** (Gemini → Ollama, **zero Anthropic quota**) — already
  proven live in the `factcli`, `standup`, and `software-arch` F→A proofs.
- **Tiered depth** — a cheap scan first (registry metadata + AST-only KG); deep
  semantic KG + tooling generation only on high-value (T1) repos.
- **Pay only for change** — the caching above means the steady-state cost is the
  cost of the *delta*, not the corpus.

### Most up-to-date — freshness is a loop, not a snapshot
- **SHA-pin, then poll.** The registry pins each repo by full 40-char SHA; a
  scheduled cadence (loopeng's `scheduler/heartbeat` + `schedule` group) polls
  upstream HEAD, and on a new SHA re-pins and re-ingests **only the delta**.
- **understand-anything's git hooks** already auto-refresh the KG on commit; the
  net-new work is extending that trigger to **also regenerate the tooling** (today
  only the KG refreshes — see the gap).
- Honest status: `schedule tick` currently *reports* what is due; live execution is
  the same roadmap item as elsewhere in this repo.

### Future-proof — build to the loop contract, not the recipe
- **Data as the source of truth** — `cited-repos.yaml` (SHA-pinned, license-gated,
  tiered) so the queue evolves without code changes.
- **Protocol seams, never a fork** — a new target type is a new `Domain` binding a
  `Factory`+`Judge`; the controller never changes (KTD1). Recipes churn in years;
  the generate→grade→update *contract* has a 30-year half-life.
- **Open distribution formats** — SKILL.md + MCP outlive any single harness; a
  capability published as a git-hosted SKILL.md works across Claude Code, Codex,
  Cursor, Hermes, gemini-cli alike.
- **License-gate at the source** — no-license repos are `emit_tooling: false`, so
  the hub never accretes legal debt it must later unwind.

## The gap (the only net-new work)

The inventory is honest that three things do **not** exist yet:

1. **A `ToolingJudge` + `Domain`** that grades *generated agentic tooling* against
   the KG: "does this skill/plugin/MCP actually do what its SKILL.md claims, and is
   it faithful to the repo's real structure?" This is the requisite-variety grader
   for the tooling axis — the single highest-leverage build.
2. **A tooling `Factory` that emits a skill/plugin/MCP** (not just a Click CLI),
   keyed off the KG.
3. **A freshness link KG→tooling** — regenerate the *tooling* (not only the KG) when
   the repo changes.

Everything else composes from parts that already ship.

## Roadmap (decomposed — one verified step per unit)

- **U1 (shipped):** the `docs/cited-repos.yaml` registry (SHA-pinned, license-gated)
  + this plan.
- **U2 — knowledge half (SHIPPED, live):** a real knowledge graph for a cited repo,
  built deterministically (graphify AST path, **no LLM**, near-free, reproducible via
  `scripts/build_repo_kg.py`). First target: **HarnessX** — chosen over the doc's
  original `cli-anything` example as the cheapest on-topic first proof (small + Python
  + the most direct harness-foundry fit), to de-risk before the large T1 repos.
  Result: **584 files → 6317 nodes, 21715 edges** across real edge types
  (uses/calls/contains/method/inherits/imports); the graph correctly surfaces
  HarnessX's event-driven architecture (the `events_*` nodes, `MultiHookProcessor`,
  `HarnessConfig`, `HarnessJournal` are its structural hubs). Confidence is honestly
  split EXTRACTED (literal AST) vs INFERRED (heuristic edges). Evidence:
  `docs/hub/kg/harnessx/`.
  - **U2 — tooling half (BLOCKED, honest):** the generate-frontier factory
    (`cli-anything`) is **not installed on this machine**, and this repo's own proofs
    already note the generate frontier is deferred; there is also no `ToolingJudge`
    yet (U3). So a *graded generated tool* proof is not shippable today — building it
    would mean fabricating a green. The tooling half waits on U3+U4 below.
- **U3:** the `ToolingJudge` + a `tooling` `Domain` (the gap, item 1) — grade a
  generated skill for claim-fidelity + repo-faithfulness.
- **U4:** the tooling `Factory` (gap item 2) — emit a SKILL.md/MCP keyed off the KG.
- **U5:** the freshness link (gap item 3) + wire `schedule` to live execution.
- **U6:** the graph-of-graphs — union the per-repo KGs, cross-link expert↔repo↔tool,
  expose over MCP; render into the existing showcase.

## Adversarial check (Debunker / Executor lenses)

- **"Isn't this just a scraper that vendors other people's repos?"** No — nothing is
  vendored (KTD1 wrap-don't-fork); the outputs are a *derived* KG and *newly
  generated* tooling, license-gated so no-license repos yield study-only KGs.
- **"Grading generated tooling is hand-wavy."** Correct today — that's exactly why
  U3 (the `ToolingJudge`) is the gating build, not an afterthought; until it exists,
  the honest state is "KG shipped, tooling ungraded → not published."
- **"Smallest step tomorrow?"** U2: run one T1 repo through understand-anything +
  `cli-anything build` + the loop, record the proof. If that single before/after is
  not reproducible, the factory isn't real yet — and we say so.
