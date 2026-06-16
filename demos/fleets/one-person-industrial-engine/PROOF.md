# one-person-industrial-engine — graduated to a real fleet demo (live F → A × 2)

The **one-person-industrial-engine** recipe graduated to a runnable, `live_verified`
demo backed by a **real coordinated fleet run** — the first end-to-end exercise of
the plan-006 fleet layer together with the loop. One person states a goal; a fleet
of self-improving loops, one per product slice, converges each slice to Grade A in
dependency order, routing each slice's outcome downstream.

## Result (real fleet run, 2026-06-16)

Fleet status: **converged**. Both slices reached A from a buggy baseline; the
dependent slice ran *after* its dependency and received its outcome as upstream
context (deterministic feedback routing, no LLM).

| slice | depends on | trajectory | grade | upstream received |
|---|---|---|---|---|
| **product-api** (factcli) | — | `F → A` | A | 0 |
| **daily-digest** (standup) | product-api | `F → A` | A | 1 (product-api's outcome) |

- **Coordinator:** `orchestration/coordinator.run_fleet` — topological waves over
  `autonomous/parallel.run_parallel` (each slice in its own git worktree).
- **Referee:** real `cli-judge` per slice (the `proof` and `automate-your-job`
  suites). **Refiner:** free-tier `FallbackLLMRefiner` (Gemini, no Anthropic).
- **Recorded** the headline (dependent) slice via `loop-anything demo record
  one-person-industrial-engine --from <run_id>` — the only path to `live_verified`
  (KTD2). The hub card shows that slice's real `F → A`; this report is the
  full-fleet evidence (see `fleet-report.txt`).

## Why a fleet, not one loop

The recipe's promise was "ship what used to need a team." The honest realization
is a *coordinated* fleet: each product slice is its own graded loop, run in
dependency order, with upstream outcomes routed into downstream briefs — the human
states the goal and confirms; the fleet does the repetitive build. The two slices
here reuse the proven self-contained targets (`demos/targets/factcli`,
`demos/targets/standup`) as stand-in product slices.

## Reproduce

Same setup as `demos/targets/standup/PROOF.md` (editable cli-judge + the `proof`
and `automate-your-job` suites in the checkout + a free LLM), then drive
`orchestration.coordinator.run_fleet` with a 2-item spec
(`product-api`, `daily-digest` depends_on `product-api`), each item's runner a
`LoopController` over the slice's worktree path, and
`loop-anything demo record one-person-industrial-engine --from <slice run_id>`.
