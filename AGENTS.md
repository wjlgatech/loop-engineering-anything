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
| `src/loopeng/config.py` | budgets, convergence knobs, dependency table |
| `src/loopeng/preflight.py` | dependency detection (per-mechanism); `missing_for_refine` (no factory) |
| `src/loopeng/router.py` | target → lane classification (U3) |
| `src/loopeng/memory/` | SQLite run history + trend/plateau/recurring queries (U2); `runs.finished` wall-clock |
| `src/loopeng/adapters/` | contracts, `safety.py` (subprocess/jail/env-prune), factory + judge shells (U4/U5), `compound_engineering.py` (`/ce-work` refiner), `llm_refiner.py` (claude-free fallback-chain refiner) |
| `src/loopeng/adopt.py` | catalog tool adopter — venv-isolated, env-pruned, full-SHA-pinned (proof pipeline U1, KTD7) |
| `src/loopeng/proof.py` | `ProofPack` builder + `StoreBackedCompounder` (proof pipeline U3) |
| `src/loopeng/loop/` | controller, convergence, brief, compound, `GitCheckpoint` (U6) |
| `src/loopeng/autonomous/` | research report + autonomous runner; `run_refine_loop` (refine-only, proof pipeline U2) |
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
   absorbs jitter if a future judge is noisy.

The judge adapter is pinned to the real `report.json` (`safety_blocker`, `D1..D5`
dims, `--out`) and verified against an installed `cli-judge`. Remaining live work:
the factory side — CLI-Anything generation is an agentic `claude -p "/cli-anything
…"` skill, and CLI-Printing-Press needs a Go toolchain — plus a full agentic
generate+refine e2e (`docs/e2e-runbook.md`). The controller core stays untouched.

project_tracker: github
