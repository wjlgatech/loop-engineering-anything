# AGENTS.md

Agent-facing guide for `loop-engineering-anything`. Read this before editing.

## What this is

A **loop orchestrator** that turns any target (a service/API or a local
codebase) into a self-improving, agent-native CLI by driving four external tools
around a closed feedback loop: route → generate → judge → refactor → re-judge →
compound. The novel surface is the controller + memory + convergence policy, not
another CLI generator. See `README.md` for the thesis and `docs/plans/` for the
implementation plan.

## Architecture boundaries

- **Wrap, don't fork (KTD1).** The four tools (CLI-Printing-Press, CLI-Anything,
  CLI-Judge, compound-engineering) are installable dependencies invoked behind
  adapters. Never vendor or fork them into this repo.
- **The controller depends only on protocols** in `src/loopeng/adapters/base.py`
  (`Judge`, `Refiner`, `Compounder`, `Checkpoint`, `Factory`). It must never call
  a real external CLI directly — that keeps loop dynamics testable against
  recorded verdicts. Concrete tool bindings live in `src/loopeng/adapters/`.
- **Quality comes only from CLI-Judge (KTD4).** The controller never inspects
  code patterns to judge quality — only the `Verdict` parsed from `report.json`.
- **Safety is unbypassable (KTD5/R3).** A safety-failing verdict is a terminal
  `BLOCKED_SAFETY` state that rolls back and never ships. Do not add a path that
  exits `BLOCKED_SAFETY` into a ship/accept.
- **Adoption isolates the install, not just the files (KTD7).** The catalog
  adopter runs third-party `pip`/`npx` code at install time. It MUST install into
  an isolated dir, pass a credential-pruned `env=` (no ambient `ANTHROPIC_API_KEY`
  etc. reaching the subprocess), and pin by a full 40-char commit SHA from an
  allowlisted host. Never widen the allowlist or accept a tag/branch ref.
- **Verified status is record-only (KTD2).** A card flips to `live_verified`
  ONLY via `demo record` / `demo proof` against a real run. Never hand-edit a
  fixture to `live_verified`, and never record a `blocked_safety` run as a
  passing proof.
- **Maker ≠ checker is enforced, not assumed (U17/R6/R10/KTD6).** Before any
  loop runs, `loop.integrity.assert_loop_integrity` fails closed if the refiner
  (maker) and judge (checker) are the same object, if a referee path lives
  inside the maker's write surface, or if the held-out grade seeds overlap the
  maker's dev seeds. A `CONVERGED` result is a *claim*: `RunResult.shippable`
  is gated by the human-confirm `VerificationGate` (ON by default). Do NOT add a
  caller-settable bypass — the only bypass keys on the CI-infrastructure env var
  for **attended** runs; **scheduled** runs stay confirm-required regardless of
  `CI`, so a scheduler can't silently auto-ship.

- **Three deliberate non-gaps vs the generic agent loop.** These are design
  choices, not omissions — do not "fix" them. (1) **Outer-loop sovereignty:** we
  govern the outer loop and referee the refiner's *output*, never its inner
  tokens; the inner loop is a swappable vendor behind the `Refiner` protocol —
  do not instrument it. (2) **Single referee of record:** quality comes only from
  CLI-Judge's `Verdict` (KTD4); never add a second quality source (a refiner
  self-report, an inner-confidence signal) — it would let a maker grade its own
  work and collapse maker≠checker. (3) **Gated human confirm:** confirmation
  gates *shipping*, not mid-loop iteration; the gate's verdict is recorded
  write-only and never feeds back into shippability. Full rationale +
  failure-mode-per-choice: `docs/solutions/outer-loop-non-gaps.md`.
- **Fleet orchestration is a loop engine, not an Agent IDE (plan-006).** The
  `orchestration/` layer coordinates our own self-improving target-loops
  (`run_loop`/`run_refine_loop`), not generic coding agents — the runner contract
  enforces it. We forgo a GitHub-native reaction system on purpose; cross-item
  feedback is the referee verdict + routed outcomes, and a Phase-A dependency is
  advisory context, not code inheritance. Fleet-level invariants hold: quality
  only from the per-worker referee, `BLOCKED_SAFETY` escalated never auto-merged,
  `confirm_convergence` the sole shippability authority. Rationale:
  `docs/solutions/fleet-orchestration-boundary.md`.

## Proof pipeline (refine-only)

`loop-anything demo proof <id>` adopts a published catalog CLI as a *baseline*,
runs the refine-only loop (`run_refine_loop` → unchanged `LoopController.run`,
whose initial judge is the "before"), builds a `ProofPack`, and records a
`live_verified` card with a before/after proof. This proves the **refine loop**,
not the generate frontier (which stays deferred). A per-target CLI-Judge adapter
at `demos/adapters/<id>.py` is required.

**The refiner is pluggable** — the controller depends only on the `Refiner`
protocol, so the refine engine is selectable:
- `--refiner claude` (default): `/ce-work` via `claude -p` — the documented brain;
  needs the compound-engineering plugin + the `claude -p` quota.
- `--refiner llm`: `FallbackLLMRefiner` — any OpenAI-compatible endpoint with a
  free-tier fallback chain (NIM → Groq → Gemini → Ollama, per the `free-llm`
  design). **No claude, no quota.** Edits are jailed full-file rewrites; model
  output is never executed. Use this to run a real proof while the `claude -p`
  quota is closed.

## Layout

| Path | Purpose |
|---|---|
| `src/loopeng/config.py` | budgets, convergence knobs, dependency table; `VerificationGate` (human-confirm gate, ON by default, CI-bypass for attended runs only — plan-004 U17) |
| `src/loopeng/preflight.py` | dependency detection (per-mechanism); `missing_for_refine` (no factory) |
| `src/loopeng/router.py` | thin shim → `domains.REGISTRY.resolve`, adapts to legacy `LaneDecision` (U3; registry-backed plan-004 U11) |
| `src/loopeng/domains/` | domain SDK: `Domain` plugin protocol + `DomainRegistry` (classify→resolve, supersedes router heuristics); `software.py` re-homes service/codebase lanes as registered domains. A new domain is a `register()`, never a controller/router edit (plan-004 U9/U11, KTD1/R11) |
| `src/loopeng/domains/physical_ai/` | physical-AI-in-sim domain (plan-004 Phase B): `sim_judge.py` `SimJudge` referees a policy in sim over a **secret held-out** seed set → `Verdict`; `safety_profile.py` centralizes the CMDP cost gate (`derive_safety_ok`, KTD2). Sim is gated (skip-not-fail); reporting bound to "sim performance only" (R12). Adopt-actuator + registration land in U13 (U12) |
| `src/loopeng/memory/` | SQLite run history + trend/plateau/recurring queries (U2); `runs.finished` wall-clock; `iterations.score` continuous signal + score-aware `is_plateaued(on_score=)` (plan-004 U9/U10); concurrency-safe for parallel fan-out — writes serialized through one shared connection + `RLock` in WAL mode (plan-004 U16, R9) |
| `src/loopeng/adapters/` | contracts, `safety.py` (subprocess/jail/env-prune), factory + judge shells (U4/U5), `compound_engineering.py` (`/ce-work` refiner), `llm_refiner.py` (claude-free fallback-chain refiner) |
| `src/loopeng/adopt.py` | catalog tool adopter — venv-isolated, env-pruned, full-SHA-pinned (proof pipeline U1, KTD7) |
| `src/loopeng/connectors/` | actuator layer — `Connector` protocol (structured `act(payload)`, never shell-interpolated) + install/credential isolation boundary: strict allowlisted `env=` (`minimal_env`), full-SHA pin, install outside the worktree, credentials by name only; one reference connector (plan-004 U15, KTD8/R8). Optional/injected — the controller never imports it (KTD7) |
| `src/loopeng/proof.py` | `ProofPack` builder + `StoreBackedCompounder` (proof pipeline U3) |
| `src/loopeng/loop/` | controller, convergence, brief, compound, `GitCheckpoint` (U6); `integrity.py` — maker≠checker / referee-immutability / held-out-disjoint assertions + human-confirm verification gate, all fail-closed (plan-004 U17, R6/R10, KTD6) |
| `src/loopeng/autonomous/` | research report + autonomous runner; `run_refine_loop` (refine-only, proof pipeline U2); runs the U17 integrity preflight + gates `CONVERGED` via `RunResult.shippable` (`scheduled`/`confirmed`); `parallel.py` — worktree fan-out (`run_parallel`): one git worktree per target, bounded by `max_parallel`, crash-isolated, auto-cleaned (plan-004 U16, R9) |
| `src/loopeng/scheduler/` | `Heartbeat` cadence engine — durable `schedule_state`, due-calc, failure isolation, resume anchor; runner-agnostic (injected, KTD7). `tick` (sequential) + `tick_parallel` (fans due targets through `autonomous/parallel.py` into isolated worktrees, plan-004 U16). `loop-anything schedule add/list/remove/tick` (plan-004 U14, R7) |
| `src/loopeng/orchestration/` | fleet orchestration layer (plan-006) — coordinates *many* self-improving loops under one goal ABOVE the per-target controller. `coordinator.run_fleet` runs items in topological waves over `autonomous/parallel.run_parallel` (cycles fail closed; non-converged deps block dependents; escalations PARK the fleet `awaiting_human`); `routing.py` pulls deps' outcomes into a dependent's brief via the U3 `upstream_context` seam; `escalation.py` routes only blocked/gated/stuck items to a human + `rebrief_item`; `spec.py`/`fleet_report.py` back the `loop-anything fleet` CLI. Depends only on `run_parallel` + `RunResult` + the store — the `LoopController` is untouched (KTD1). `memory/fleet_state.py` holds the lifecycle enums + transition guard. |
| `src/loopeng/demos/` | demo manifest/registry + result fixtures (validated; SSRF/traversal/secret guards) |
| `src/loopeng/showcase/` | self-contained HTML catalog generator (context-aware escaping) |
| `demos/` · `docs/recipes/` | community demo manifests + fixtures; aspirational loop recipes |
| `skills/loop-anything/` | the `/loop-anything` agent skill |

## Conventions

- Python ≥3.11, Click CLI, `pytest`, stdlib `sqlite3`, dataclasses for contracts.
- Subprocess calls MUST use an args list (never `shell=True` / f-string commands)
  and target input MUST be validated before reaching an adapter.
- Conventional commits. Run `pytest` before committing; CI runs it on every PR.

## Workflow

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
loop-anything preflight
```

Per change that alters behavior: add a `CHANGELOG.md` entry under `[Unreleased]`
and sync the docs the change touches (README, this file, the plan's tables).

## Feasibility gates (mechanism resolved; empirical validation pending)

1. **Headless refinement** — `/ce-work` and `/ce-compound` are driven via
   `claude -p` in `adapters/compound_engineering.py` (`ClaudeCodeRefiner` /
   `ClaudeCodeCompounder`). Mechanism settled; output *quality* on a real target
   is still to be measured on a live run.
2. **Grade stability** — RESOLVED empirically: the installed CLI-Judge is
   deterministic (variance probe spread 0.0), so single-run grades are safe.
   `loop-anything judge-variance` re-checks any target; `Budget.min_score_gain`
   absorbs jitter if a future judge is noisy. A continuous-score domain (set
   `Budget.target_score`) converges on the score after the unbypassable safety
   gate and plateaus on `score` (`is_plateaued(on_score=True)`); a stochastic
   referee MUST set `min_score_gain` from the variance probe (plan-004 U10).

The judge adapter is pinned to the real `report.json` (`safety_blocker`, `D1..D5`
dims, `--out`) and verified against an installed `cli-judge`. Remaining live work:
the factory side — CLI-Anything generation is an agentic `claude -p "/cli-anything
…"` skill, and CLI-Printing-Press needs a Go toolchain — plus a full agentic
generate+refine e2e (`docs/e2e-runbook.md`). The controller core stays untouched.

project_tracker: github
