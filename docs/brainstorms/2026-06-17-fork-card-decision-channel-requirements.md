---
date: 2026-06-17
topic: fork-card-decision-channel
---

# Fork-Card decision channel — requirements

## Summary

Make a build decision a first-class artifact. When the spec/northstar doesn't determine a choice, the coding agent emits a typed **Fork-Card** instead of stalling. **v1 targets the autonomous (headless) regime**: the agent self-reports the fork in its structured output and keeps building a reversible default; the supervisor resolves it and reverses via the loop's existing rollback. The card is the gradable unit the rest of the supervised loop consumes. The interactive regime is deferred (see Scope Boundaries) because Claude Code hooks cannot inject a menu answer today.

---

## Problem Frame

Today the coding agent's mid-build decisions go one of two bad ways. In the **interactive TUI** the user runs by hand, the agent pauses with a "which option?" menu and waits — the user babysits. In the **autonomous loop**, the refiner already drives the agent as `claude -p --permission-mode acceptEdits` (`src/loopeng/adapters/compound_engineering.py:55,93`), which is non-interactive: the agent never pauses, it silently picks a default for every fork and moves on. The first costs the user's attention; the second makes ungrounded decisions invisibly, with no record and no grounding in the user's taste or the project goal.

The supervised loop the user wants ("see the end result, give feedback, don't prompt along the way") cannot exist until these forks become *visible, typed, and routable*. This is the keystone: every downstream piece (persona scoring, escalation triage, the decision ledger, spec-patching) consumes the Fork-Card. Without it there is nothing to ground, grade, or review.

---

## Key Decisions

**KD1 — Spec-ambiguity is the emission trigger.** A Fork-Card is emitted only when the northstar/spec doesn't determine the choice (silent, vague, or self-contradictory). The spec is the determinant; choices it settles need no card. This self-bounds volume — a flood of cards *is* the signal the spec is thin — and ties the channel to the living-spec idea downstream.

**KD2 — One card type; headless capture is v1.** Headless can't fire a question menu (no human present), so the agent self-reports the fork in its structured output. This is the autonomous keystone and the only capture path in v1. The interactive path (intercepting Claude Code's `AskUserQuestion` menu) is deferred: a `PreToolUse` hook can deny/allow a tool but **cannot inject a substitute result**, so it can't silently auto-answer the menu from the twin. The clean version needs the Agent SDK `canUseTool` callback — out of scope to keep v1 on the bare CLI.

**KD3 — Headless resolution timing.** The agent builds the most reversible reasonable default and continues; the supervisor reverses it asynchronously via the loop's existing regression rollback (`src/loopeng/loop/controller.py:12,197`).

**KD4 — Resolution policy is a three-step cascade.** Spec determines → no card. Spec silent + twin grounded (with a citation) → auto-resolve. Spec silent + twin ungrounded → escalate (interactive: to the human now; headless: record as unresolved with a reversible default and flag for end-review).

**KD5 — The resolver calls a pluggable oracle; it is never the referee.** The twin's scoring internals are out of scope here — the resolver depends on an oracle *interface*. The resolver/oracle that answers a fork must be distinct from the `CLIJudge` referee that grades the build, extending the existing maker≠checker invariant (`src/loopeng/loop/integrity.py:43`) to oracle≠checker.

**KD6 — A wrong default is invisible to the referee; safety depends on the spec-patch downstream.** The referee grades toward the spec, and the spec was silent exactly where the fork was — so a wrongly-defaulted fork won't be caught by grading. The backstop is the living-spec patch (separate brainstorm) plus the end-review flag (R5). This keystone ships the card and an explicit handoff point for the patch, not the patch itself.

---

## Actors

- **A1. Coding agent (maker)** — Claude Code, driven headlessly via `claude -p` or run interactively. Emits or surfaces forks.
- **A2. Supervisor** — the loop-side consumer that reads Fork-Cards, invokes the resolver, and reverses defaults via rollback.
- **A3. Resolver** — maps a Fork-Card to a chosen option via the spec → oracle → escalate cascade.
- **A4. Oracle (out of scope to build)** — the digital twin behind a pluggable interface; returns a grounded choice + citation or "no grounding".
- **A5. Human** — sets the northstar at the start, receives escalations and the end-review.

---

## Key Flows

**F1. Headless fork (the autonomous path).**
**Trigger:** the agent reaches a choice the spec doesn't settle.
1. Agent emits a Fork-Card and records the most reversible reasonable default as `chosen_default`.
2. Agent keeps building on that default — no pause.
3. The refiner parses emitted cards from the agent's output and records them for the run.
4. The supervisor runs the resolver per card; if the resolver's choice differs from `chosen_default`, it marks the card for reversal.
5. A reversal triggers the loop's existing regression rollback.

**F2. Interactive fork (the at-keyboard path) — DEFERRED.** Out of v1 scope (see Scope Boundaries / KD2). Documented for the follow-up: intercept `AskUserQuestion`, build a Fork-Card, resolve, and inject via the Agent SDK `canUseTool` callback.

---

## Requirements

### The card contract

R1. Define a typed `ForkCard` with: `id`; `options[]` (each an option id, label, short description); `spec_clause` (the clause/section consulted and why it didn't settle the choice); `chosen_default` (option id or null); `reversibility` (`reversible` | `hard_to_reverse` | `irreversible`); `blast_radius` (`local` | `module` | `cross_cutting`); `basis` (oracle citation references, or `unresolved`); `regime` (`headless` | `interactive`); `created_at`.

R2. Fork-Cards serialize to a stable on-disk format the supervisor consumes, append-only per run.

### Emission — headless

R3. The headless `/ce-work` prompt convention instructs the agent: when a decision is not determined by the spec/northstar, emit a Fork-Card rather than asking, pick the most reversible reasonable default, record it as `chosen_default`, and keep building.

R4. The refiner extracts emitted Fork-Cards from the agent's output, extending the existing `--output-format json` parse path (`parse_token_cost` in `src/loopeng/adapters/compound_engineering.py`), and records them for the run.

R5. A fork that is spec-silent and has no oracle grounding is recorded with `basis: unresolved` (a reversible default may still be chosen) and flagged for end-review.

### Emission — interactive (DEFERRED)

R6. *(Deferred to follow-up.)* Intercept the agent's `AskUserQuestion` menu and construct a Fork-Card from the question and its options.

R7. *(Deferred to follow-up.)* Inject a grounded answer via the Agent SDK `canUseTool` callback; otherwise pass the question through to the human. Blocked in v1 by the Claude Code hook limitation (KD2).

### Resolution and integrity

R8. A resolver maps a Fork-Card to a chosen option via the cascade: spec determination → oracle grounding (cited) → escalate. The resolver depends on an oracle *interface*; a stub/no-grounding oracle is acceptable for this unit.

R9. When the supervisor's resolved choice differs from a headless `chosen_default`, reversal routes through the loop's existing regression rollback rather than a new mechanism.

R10. Assert the resolver/oracle is distinct from the `CLIJudge` referee (oracle≠checker), mirroring `assert_maker_distinct_from_checker`.

---

## Acceptance Examples

**AE1. Covers F1.** Spec clause covers the choice → agent proceeds, no Fork-Card emitted.

**AE2. Covers F1, R3, R4.** Spec silent, oracle grounded → agent emits a card, resolver picks the cited option, build continues; card recorded with `basis` = citation.

**AE3. Covers F1, R5.** Spec silent, no grounding → agent emits a card with a reversible `chosen_default` and `basis: unresolved`; card flagged for end-review.

**AE6. Covers R9.** Supervisor reverses a headless default → regression rollback fires.

**AE7. Covers R10.** A configuration where the oracle equals the referee → the integrity assertion raises before any run.

---

## Scope Boundaries

### In scope (v1)

The `ForkCard` type and on-disk format, the **headless** self-report capture path, the resolver cascade behind a pluggable oracle interface, reversal via existing rollback, and the oracle≠checker assertion.

### Deferred / adjacent

- **Interactive capture path** — intercepting `AskUserQuestion` and auto-answering from the twin. Blocked on the bare CLI (hooks can't inject a tool result); the clean build needs the Agent SDK `canUseTool` callback. Checkpoint with the user before starting it.
- **Oracle internals** — how the twin scores options and produces citations (ideation idea #2).
- **Escalation triage** — reversibility/blast-radius gating, the question budget, the merge-readiness pack (#4).
- **Decision ledger** — persisting cards across runs and replaying by fingerprint (#5).
- **Living-spec patch** — turning a resolved card into a spec clause the referee can grade (#6). KD6 makes this the load-bearing downstream safety net.
- **Fleet / multi-build** — resolving a fork once and routing it across parallel slices (deferred).

---

## Dependencies / Assumptions

- **Claude Code hook limitation (validated 2026-06-17).** A `PreToolUse` hook *does* fire on `AskUserQuestion` and receives the questions/options, but it can only allow/deny/ask — there is **no field to inject a substitute tool result**. So a hook cannot silently auto-answer the menu. The only clean injection path is the Agent SDK `canUseTool` callback. This is why the interactive regime is deferred and v1 is headless-only.
- **Headless self-report relies on prompt-convention reliability** — the agent honestly surfacing forks it could otherwise decide silently. Accepted for v1, with the spec-patch (#6) and end-review flag (R5) as backstops. There is no hard intercept in headless mode equivalent to the interactive hook.
- **Reused as-is:** regression rollback (`src/loopeng/loop/controller.py`), integrity assertions (`src/loopeng/loop/integrity.py`), the `--output-format json` parse path (`src/loopeng/adapters/compound_engineering.py`).

---

## Outstanding Questions

### Deferred to Planning

- Exact on-disk Fork-Card format (sidecar file vs. embedded in the json result envelope).
- How the headless agent signals a Fork-Card within `--output-format json` output (sentinel block vs. a written sidecar the refiner reads).
- The oracle interface signature (inputs the resolver passes; shape of the grounded-choice/no-grounding return).

---

## Sources / Research

- `docs/ideation/2026-06-17-supervised-coding-loop-ideation.html` — idea #1 (keystone), plus #2/#4/#5/#6 (the consumers this card feeds).
- Repo primitives: `src/loopeng/adapters/compound_engineering.py`, `src/loopeng/loop/controller.py`, `src/loopeng/loop/integrity.py`.
- External: OpenAI Auto-review (separate-reviewer precedent), PersonaTwin (preference hallucination / drift bounds), Kiro SDD (Constitution > Spec > Tasks), Microsoft red-team (consent-fatigue / Goodhart failure modes).
