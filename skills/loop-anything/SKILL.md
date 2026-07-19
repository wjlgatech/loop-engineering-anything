---
name: loop-anything
description: >
  Turn any target (a service/API URL, HAR, or OpenAPI spec; or a local
  codebase/repo) into a self-improving, agent-native CLI — then keep improving
  it. Routes the target to the right factory, generates the tool, grades it with
  an INDEPENDENT referee (CLI-Judge), and drives a refactor -> re-judge loop
  until Grade A, a safety block, or budget exhaustion -- then compounds the
  learnings and emits a research report. Also runs fleets, records before/after
  proofs, and carries durable cross-run memory. Use for "make X agent-native and
  keep improving it", or the overnight "going to the beach" autonomous run.
---

# loop-anything

`loop-anything` is the **inner loop** of loop engineering: it converges a *single
artifact* to an independently graded bar. It is the complement of an **outer
loop** (schedule/triage/escalate a repo over time, e.g.
`cobusgreyling/loop-engineering`) — see `docs/solutions/integrate-loop-engineering.md`.

It is a **loop orchestrator**, not a CLI generator. It drives external tools
around a closed feedback loop and never judges quality itself:

| Stage | Tool (behind an adapter) | Role |
|---|---|---|
| route + generate | CLI-Printing-Press / CLI-Anything | build the agent-native CLI |
| judge | **CLI-Judge** | grade it against reality (`report.json`) — the *only* quality source |
| refactor | `/ce-work` (or an LLM/chain refiner) | fix the lowest-scoring dimensions |
| compound | `/ce-compound` | record the learning + a regression test |

## The operating discipline (survival-tested — read once)

Three centuries of feedback-control history converge on rules that decide whether
an improvement loop compounds or diverges. This engine is built around them; hold
them when you drive it:

1. **The grader is the product.** Every improvement loop that died in history
   (genetic programming, MDA round-trip, autonomic computing, self-modifying
   expert systems) died at the *grading* step, not generation. Quality comes
   ONLY from `CLI-Judge`'s `Verdict` (KTD4) — never from the refiner's
   self-report or a code-pattern heuristic.
2. **Give the grader requisite variety** (Ashby). A grader that can't distinguish
   as many failure modes as the generator can produce gets gamed. Use
   `judge-variance` to measure grade stability; hold out checks the generator
   never sees so a *plausible* patch can't pass as a *correct* one (GenProg's
   near-death lesson).
3. **Measure, don't self-report** (Watt→Deming). The loop closes on a measured
   error signal, and the corrector (refiner/maker) must be a *different* object
   from the referee (judge/checker) — enforced fail-closed by
   `loop.integrity.assert_loop_integrity`, not assumed.
4. **Prove convergence at design time** (Maxwell/Nyquist/Bode). Bound loop gain
   with a budget (iterations, wall-clock, plateau patience) so the loop can't
   oscillate or run away — the #1 documented cause of abandonment and runaway
   token bills.
5. **Dense signal beats binary.** The refactor step needs partial-credit
   dimensions + specific failure evidence (`Verdict.dims`, `failing_fixtures`),
   not red/green — that's the difference between a gradient and a coin flip.
6. **Persist memory across runs** (MAPE-K's K). The learnings corpus is what
   upgrades a retry loop into an *improvement* loop; carry it with
   `learnings export/import`.
7. **Close the round trip.** If a human edits the artifact, the next run grades
   the edited state as new ground truth. A loop that only works on untouched
   generated code gets abandoned (MDA's death).

## Preconditions

Run preflight first — it detects all four dependencies and fails fast if one
required for your lane is missing:

```
loop-anything preflight
loop-anything preflight --lane service     # exit 1 if the service lane is blocked
loop-anything preflight --json
```

The compound-engineering plugin is detected as a Claude Code skill, not a PATH
binary. If auto-detection can't confirm it, set
`LOOPENG_ASSUME_COMPOUND_ENGINEERING=1`.

## Command surface

### Single-target loop

```
loop-anything run <target> --goal "<goal>" [--lane service|codebase]
    [--refiner chain|claude|llm] [--judge-adapter PATH] [--judge-registry DIR]
    [--workspace DIR] [--max-iterations N] [--confirm/--no-confirm] [--scheduled]
loop-anything status                       # list recorded runs
loop-anything report <run_id> [--json]     # the research report for a run
loop-anything judge-variance <tool_path> --adapter PATH [-k 5]
```

`<target>` = a URL, a `.har`, an OpenAPI spec, or a local dir / git repo. The
lane is auto-classified; `--lane` forces it. `judge-variance` re-judges an
unchanged tool K times to measure grader stability and recommend a
`min_score_gain` threshold (rule 2 above).

### Fleet — dependency-ordered multi-target

```
loop-anything fleet run <spec_path> [--goal ...] [--repo .]
    [--worktrees-root .loopeng/fleet-worktrees] [--dry-run] [--refiner ...]
loop-anything fleet status <fleet_id>
loop-anything fleet report <fleet_id> [--json]
loop-anything fleet escalations <fleet_id>
```

Executes in topological waves over per-item git worktrees; upstream outcomes
route downstream. `--dry-run` materializes the fleet without executing.

### Demos & before/after proofs

```
loop-anything demo list [--domain ...] [--json]
loop-anything demo show <id>
loop-anything demo run <id> [--workspace DIR]
loop-anything demo record <id> --from <run_id>     # flip a card to live_verified
loop-anything demo validate                         # CI gate (exit 1 on failure)
loop-anything demo proof <id> --catalog cli-anything|printing-press \
    --name <entry> --sha <full-40-char-sha> --install-kind pip_git_subdir|pp_binary \
    [--refiner claude|llm] [--dry-run]
loop-anything showcase --out showcase.html [--base-url URL]
```

`demo proof` adopts an already-generated catalog CLI as the "before" baseline,
runs the loop, and records a `live_verified` card with the before/after grade,
per-dimension diff, iterations, and compounded regression tests. A card flips to
`live_verified` ONLY via `demo record`/`demo proof` against a real run (KTD2) —
never hand-edit a fixture.

### Durable memory (cross-run learnings)

```
loop-anything learnings export [--target ...] [--redact] [-o out.jsonl]
loop-anything learnings import <path.jsonl>
```

Stable sorted-key JSONL, one object per line; `--redact` strips URLs/paths/ids;
import is idempotent and sanitize-on-write. This is the portable form of rule 6.

### Scheduling (cadence)

```
loop-anything schedule add <target> --interval <seconds> [--goal ...] [--lane ...] [--domain ...]
loop-anything schedule list
loop-anything schedule remove <target>
loop-anything schedule tick        # reports what is DUE now — does NOT execute yet
```

> **Honest status:** `schedule tick` currently *reports* the due set (durable
> cadence in the `schedule_state` table) so an operator or external cron can see
> it; it does **not** run the loop yet — live execution rides the same injected
> runner as `run` and is on the roadmap. Wire an OS cron / GitHub Action to call
> `run` per due target until then.

## Autonomy ladder (how far the loop acts on its own)

Adopted from the outer-loop vocabulary. Earn autonomy; never assume it.

- **L1 — report-only.** Grade + report, no shipping. `run --no-confirm` produces
  a `CONVERGED` *claim* + research report; a human reads it.
- **L2 — assisted (default).** Converged ≠ shippable until a human clears the
  `VerificationGate`. This is the safe default for real targets.
- **L3 — unattended.** For trusted, reversible targets only. `--scheduled` marks
  an unattended run and **stays confirm-required regardless of `CI`** — a
  scheduler can never silently auto-ship (anti-cognitive-surrender).

## Safety & governance

- **Terminal safety (unbypassable, R3/KTD5).** A safety-failing `Verdict` is a
  terminal `BLOCKED_SAFETY` state that rolls back and never ships. There is no
  path from `BLOCKED_SAFETY` to accept/ship.
- **Workspace jail + checkpoints.** Code changes apply only inside the workspace
  boundary (`within_workspace`); every iteration is a git checkpoint so a
  regression rolls back cleanly.
- **Isolated, credential-pruned adoption (KTD7).** The catalog adopter installs
  third-party code into an isolated dir with a credential-pruned env and pins by
  full 40-char SHA from an allowlisted host.
- **Budget guards (Config.Budget).** `max_iterations` (10), `plateau_patience`
  (3) + `plateau_pivots`, `token_budget` (advisory), `max_wall_seconds`
  (universal backstop), `min_score_gain`, `max_tool_retries`. These are the
  convergence guardrails that answer the runaway-loop / token-burn failure mode.
- **Governance format.** Path denylist + auto-merge allowlist live in
  `gate.yaml` (machine-readable twin of the safety rules).

## Failure modes to watch (and the guard for each)

| Failure mode | Guard in this engine |
|---|---|
| Infinite fix loop (never converges) | `max_iterations` + `plateau_patience`/`plateau_pivots` |
| Verifier theater (approves bad work) | `assert_loop_integrity` (maker≠checker) + `judge-variance` |
| Token burn / runaway | `token_budget` + `max_wall_seconds` |
| Plausible-but-wrong patch (overfit to visible checks) | held-out grade seeds; adversarial fixtures |
| Cognitive surrender (auto-ship on green) | `VerificationGate` ON by default; `--scheduled` stays gated |

## Status (honest)

- **Shipped end-to-end:** `run` (routes → generates via factory → resolves an
  out-of-jail judge adapter → drives the refine loop), `fleet`, `demo`/`proof`,
  `learnings export/import`, `showcase`, `judge-variance`, budget/convergence,
  checkpoint/rollback, maker≠checker integrity, physical-AI domain.
- **Roadmap (not yet built):** live scheduled execution (`schedule tick` runner),
  `run --pr` "Loop-as-PR" (run on a branch, open a PR whose body is the proof
  report), and `gate check`. See `docs/plans/2026-07-02-001` (U2/U3).
