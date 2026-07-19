# Integrate with `cobusgreyling/loop-engineering`? — decision record

**Date:** 2026-07-18 · **Status:** decided (adopt discipline, not code) · **Scope:** whether/how to
integrate the 8.5k-star `cobusgreyling/loop-engineering` reference repo with this engine.

---

## TL;DR

**Yes — integrate the *discipline and formats*, never the code.** The two projects are the two
halves of one loop and do not compete:

| | `cobusgreyling/loop-engineering` | `loop-engineering-anything` (this repo) |
|---|---|---|
| Layer | **Outer loop** — operate a repo *over time* | **Inner loop** — converge *one artifact* to a grade |
| Job | discover work → triage → schedule → escalate | generate → judge → refactor → re-judge → compound |
| Unit | a repo / a queue of PRs & issues | a single agent-native CLI (or a fleet of them) |
| Substrate | markdown patterns + thin JS/TS CLIs (57% JS, 4% Py) | Python engine, protocol-injection architecture |
| What it ships | governance, cadence, cost model, failure catalog | an *independent grader* + convergence policy + rollback |
| Verification | describes maker/checker as a discipline | **enforces** maker≠checker as a fail-closed contract |

Their repo is the operating manual for the factory floor; ours is the one machine on it that
actually measures its own output and improves until an independent referee says stop. Their
own "broader menu" lists PR-lifecycle / CI-sweeper loops as rows to be built — those are inner
loops they describe but cannot grade. That is the seam.

**Do not vendor or fork their code** (KTD1). Adopt three things: (1) their **machine-readable
governance formats**, (2) their **autonomy ladder** as our shipping vocabulary, and (3) their
**failure-mode catalog** as convergence guardrails — most of which our engine already embodies.

---

## Why integrate (the evidence)

### 1. History says the grader is the product — and that is our bet, not theirs

The 30-year and 300-year survival sweeps agree on one thing with unusual force:

> **Every dead improvement loop died at the *grading* or *round-trip* step, never at generation.**

- **Genetic programming** for general software synthesis — died: uninformative fitness (random
  mutation gets almost no gradient from "does the whole program work"). The LLM era fixed the
  *generator*, not the loop. ([lethain](https://lethain.com/genetic-programming-a-novel-failure/))
- **MDA / executable-UML round-trip** — died: humans edited the generated artifact and the loop
  couldn't absorb the edit. ([Fowler](https://martinfowler.com/bliki/ModelDrivenArchitecture.html))
- **IBM Autonomic Computing / self-modifying expert systems** — died: no verifiable definition of
  "better"; self-modification without an external trustworthy grader diverges.
- **GenProg's near-death** — the overfitting critique: a *plausible* patch that passes visible
  tests is not a *correct* one. Survived by hardening validation.
  ([GMU retrospective](https://cec.gmu.edu/news/2025-12/genprogs-decade-defining-developments-debugging))

The 300-year window names the invariant behind all of these: **Ashby's Law of Requisite Variety
+ the good-regulator theorem** — a grader can only control the loop to the extent its repertoire
matches the variety of failures the generator can produce; give the grader too little variety and
the loop optimizes into its blind spots (reward hacking). This is the single highest-leverage,
most-underused principle for agent loops, and it maps directly onto our `Judge` seam.

**Implication:** our architecture (`KTD4` quality only from `CLI-Judge`; `assert_loop_integrity`
maker≠checker/referee-immutable/held-out grade) is not a nice-to-have — it is the exact thing the
graveyard says loops need. `cobusgreyling/loop-engineering` *describes* maker/checker as a
checklist item; we *enforce* it. Integrating their vocabulary lets us claim that difference in
their own language.

### 2. The 30-day market says our lane is empty — and drift/burn is the churn driver

- The movement's front door is Steinberger's post ("design loops that prompt your agents",
  ~5–8M views), but **61% of replies were skeptical** — the market's live objection is "how is
  this not a `while-true` burning tokens?"
- The hot lanes are **runners** (Ralph family; `ralph-loop-agent` 821★; `/goal` now first-party in
  both Claude Code and Codex) and **scorers** (their `loop-audit`). Across a 16-source sweep,
  **nothing generates *and* regrades a whole CLI under an independent grader** — that lane was
  empty as of 2026-07-18.
- The documented churn drivers are **agent drift / inconsistent results**
  ([Pragmatic Engineer, ~210 devs](https://newsletter.pragmaticengineer.com/p/what-is-loop-engineering))
  and **runaway token burn** (InfoQ billing-guardrails wave; $6k-overnight and 17M-token
  incidents). Our score-trajectory-per-iteration + `max_wall_seconds`/`token_budget`/plateau
  guards answer *both* named objections directly.
- The empirically under-served dimensions in the loop-spec formalization
  ([arXiv 2607.00038](https://arxiv.org/abs/2607.00038)) are **triggering** and **durable memory** —
  our learnings-corpus JSONL export/import (U1) is aimed squarely at the memory gap.

**Implication:** integrate to *differentiate*, not to blend in. Position as "the graded, bounded,
evidence-producing inner loop" the runners lack and the scorers can't generate. Adopt their brand
vocabulary so the inevitable first question — "how is this different from the 8.5k-star repo?" — has
a one-line answer: *they score and schedule loops; we generate and converge the artifact inside one.*

### 3. It closes three real gaps in this repo (confirmed in the code)

| Gap here (confirmed) | What their repo supplies | How to adopt |
|---|---|---|
| `schedule tick` is **report-only** (`runner=lambda fire: -1`); no live scheduled execution, no cron/launchd generator | cadence patterns + `/loop`/cron primitives matrix across 8 harnesses | wire the injected runner to the autonomous loop; emit a crontab/Action from `schedule` state |
| **Loop-as-PR / PR-babysitter unbuilt** (U2, draft `2026-07-02` plan) | the PR-Babysitter pattern (discover→triage→fix→verify→notify, human gates) | build `run --pr`: run on a branch, open a PR whose body *is* the proof report on convergence |
| governance is code-only (no machine-readable gate/registry, no autonomy vocabulary) | `gate.yaml` (denylist + auto-merge allowlist + maxFiles), `registry.yaml`, **L1→L2→L3 autonomy ladder**, the **failure-mode catalog** | add a `gate.yaml`; adopt L1/L2/L3 as the `--scheduled`/confirm vocabulary; map failure modes to convergence signals |

---

## Why NOT deeper integration (the guardrails)

- **Don't vendor/fork their tools (KTD1).** They are JS/TS npm packages solving the *outer* loop;
  our engine is Python solving the *inner* loop. A dependency edge would couple release cycles for
  no capability we can't express in ~25 lines of governance format.
- **Don't add a second quality source.** Their `loop-audit` produces a *readiness score for the
  loop's setup*; that is orthogonal to `CLI-Judge`'s *Verdict on the artifact*. Never let the audit
  score feed shippability — that would collapse maker≠checker (KTD4, outer-loop-non-gap #2).
- **Don't instrument their inner tokens or ours.** Outer-loop sovereignty (non-gap #1): we referee
  the refiner's *output*, never its inner tokens. Their patterns respect the same boundary.
- **Naming risk is real.** "loop-engineering-anything" reads as a fork of the 8.5k-star repo.
  Mitigate in the README with the outer/inner-loop table above, not by renaming.

---

## Decision: three concrete adoptions

1. **Governance formats.** Add a root `gate.yaml` (path denylist, auto-merge allowlist, `maxFiles`)
   as the machine-readable twin of our safety rules — the format their `loop-gate` popularized,
   enforced here by `within_workspace` + `validate_target` + `minimal_env`. This makes our safety
   contract inspectable, not just coded.

2. **Autonomy ladder as shipping vocabulary.** Adopt **L1 report-only → L2 assisted → L3
   unattended** as the words for our confirm/`--scheduled` states. We already gate shipping behind a
   human `VerificationGate` (L2 by default) and keep `--scheduled` runs confirm-required (never
   silent L3). Naming it their way makes the guarantee legible to their audience.

3. **Failure-mode catalog → convergence guardrails.** Map their catalog onto signals we already
   have, and name the two we should build:
   - Infinite Fix Loop → `max_iterations` + `plateau_patience`/`plateau_pivots` ✅
   - Verifier Theater → `assert_loop_integrity` (maker≠checker, referee-immutable) + `judge-variance` ✅
   - Token Burn → `token_budget` + `max_wall_seconds` (universal backstop) ✅
   - State Rot → prune-on-run for `schedule_state`/`runs` (**build**)
   - Comprehension Debt Spiral → the research report per run is the human digest ✅ (surface it louder)

**Roadmap items this unlocks** (honest — not yet built): live scheduled execution (`schedule tick`
runner), `run --pr` Loop-as-PR mode, and a `loop-anything gate check` command. Tracked against the
draft `docs/plans/2026-07-02-001` (U2/U3).

**What ships now:** the expanded `skills/loop-anything/SKILL.md` (accurate to the real CLI +
survival-tested operating discipline + the adopted autonomy/governance vocabulary) and this record.

## Sources

Research provenance (four sweeps): repo deep-dive of `cobusgreyling/loop-engineering` @ v1.5.0;
`/last30days` engagement sweep (16 sources; anchors: Pragmatic Engineer, PostHog, The Register,
InfoQ, arXiv 2607.00038, vercel-labs/ralph-loop-agent); `/last30years` survival sweep (CI/CD, ML
training loop, K8s reconciliation, A/B, TDD, GenProg, chaos, PGO, MAPE-K, deep-RL + graveyard);
`/last300years` survival sweep (Watt governor, Maxwell/Nyquist/Bode, homeostasis, Shewhart/Deming
PDSA, Darwinian VSR, Ashby requisite variety, negative-feedback amplifier).
