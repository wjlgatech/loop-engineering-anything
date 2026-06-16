# One-person industrial engine (recipe)

> **Recipe — not runnable yet.** An aspirational *fleet* loop adapted from an
> AI-agency brainstorm. It depends on the fleet orchestration layer
> (`docs/plans/2026-06-16-006-feat-fleet-orchestration-layer-plan.md`, Phase A in
> progress), so it is a recipe until that layer ships.

## The reframe

The brainstorm's "One-Person Industrial Engine": a single person spins up what
used to require a company — design, build, ship — through orchestrated agents
("I had an idea Tuesday; I had customers Friday"). For a loop engine, the honest
version is a **coordinated fleet of self-improving loops**, one per product slice.

## The loop

A goal ("ship product X") decomposes into a dependency graph of slices — an API
client, a data pipeline, a docs/site, a CLI. Each slice is its own loop:
generate → judge against reality → refactor → converge to Grade A, in isolated
worktrees. The fleet coordinator runs them in dependency order, routes each
slice's outcome into its dependents' briefs, and escalates only the
high-judgment forks to the human. One person directs intelligence; the fleet does
the repetitive build.

## What it would need

- **Coordinator:** the fleet orchestration layer (plan-006) — lifecycle state,
  dependency-ordered waves, feedback routing, human-efficiency escalation.
- **Targets:** each product slice with its own CLI-Judge referee + exit criteria.
- **Exit criterion:** every slice converged-and-shippable; the human confirms the
  whole.

## Why it isn't runnable yet

Phase A of the fleet layer (the deterministic coordination plumbing) is still in
flight, and Phase B (the orchestrator brain that decomposes a vision into the
slice graph) is deferred. The per-slice loop is proven
(`demos/targets/factcli/PROOF.md`); coordinating a *fleet* of them under one goal
is the gap. When the fleet layer lands, this graduates from recipe to a real,
multi-slice demo.
