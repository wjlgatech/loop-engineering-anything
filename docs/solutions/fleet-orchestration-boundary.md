# Fleet orchestration is a loop engine, not an Agent IDE

The fleet orchestration layer
(`docs/plans/2026-06-16-006-feat-fleet-orchestration-layer-plan.md`,
`src/loopeng/orchestration/`) coordinates *many* of our self-improving loops
toward one goal. It was prompted by a comparison against Prateek Karnal's
"What Are Agent Loops, Really?" and his project Agent Orchestrator (AO). AO and
this layer share the same orchestration *pattern* — decompose a goal, run a
fleet of isolated workers, route feedback, track lifecycle, pull a human in only
for high-judgment forks. The boundary worth naming is the **worker substrate**.

## The boundary

- **AO** coordinates generic *coding agents* through an issue → PR → CI → review
  IDE loop. Its worker is a code-gen agent; its feedback is GitHub events.
- **We** coordinate our own *self-improving target-loops* — each fleet worker is
  `run_loop` / `run_refine_loop` (route → generate → judge → refactor → compound
  to convergence), graded by an independent reality-grounded referee. Our worker
  is a loop; our feedback is the referee verdict + routed upstream outcomes.

We apply the same orchestration pattern to a different substrate. That is the
distinction — not a different kind of orchestration.

## Why it's enforced, not just asserted

The coordinator's runner contract drives `run_loop` / `run_refine_loop` (which
return a `RunResult` the fleet understands), not an arbitrary agent callable. So
"loop engine, not Agent IDE" is a code constraint, not only a doc claim
(`coordinator.run_fleet`, KTD6).

## The failure mode this boundary accepts

We forgo a GitHub-native reaction system (AO's CI-failure / review-comment
injection). Our cross-item feedback in Phase A is the referee verdict + routed
upstream *outcomes*, not GitHub events, and a Phase-A dependency is advisory
context, not code inheritance (worktrees branch off `HEAD`). That is a deliberate
cost: we are a substrate-agnostic loop engine over any target, not a code-review
IDE bolted to one host. A GitHub-native lane is revisited only if a target lane
needs it.

## What stays invariant at the fleet level

- **Quality only from CLI-Judge, per worker** — the fleet never overrides a
  worker's verdict.
- **Safety unbypassable** — a `BLOCKED_SAFETY` worker is escalated, never
  auto-merged.
- **Human-confirm authority unchanged** — `confirm_convergence` (read via
  `RunResult.shippable`) is the sole shippability authority; escalation surfaces
  the borderline, it does not bypass the gate (R10 lifted to the fleet).
- **Maker ≠ checker at the fleet level** — the Phase-B orchestrator brain
  (decomposer / brief-writer) is a distinct role from any worker's judge.

See also `docs/solutions/outer-loop-non-gaps.md` (the single-loop sovereignty,
single-referee, and gated-human-confirm boundaries this builds on).
