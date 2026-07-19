# `/loop-anything` — before vs after (real graded runs)

**What "before vs after" means here.** `/loop-anything` never just generates a tool
and stops. An **independent referee** (`cli-judge`) grades the artifact against a
captured real payload from **F to A**; a **different** helper (the refiner) fixes
the lowest-scoring dimensions; the referee re-grades. Build → grade → fix →
re-grade, with every accepted fix banked as a regression test and every
no-gain change rolled back — until it hits A, a safety block, or the budget runs
out.

Because the maker and the checker are different objects (enforced by
`assert_loop_integrity`), the "after" grade is not the tool marking its own
homework. And a card only becomes `live_verified` through `demo record` /
`demo proof` on a **real** run (KTD2) — the numbers below are recorded, not typed.

**Provenance is labeled honestly.** ✅ **live_verified** = a real end-to-end run
(recorded). 🧪 **illustrative** = a recipe/expected trajectory, not yet a live run.

---

## ✅ Verified examples (real F → A runs)

All three ran on **2026-06-16**, engine `0.1.0`, refined by a **free-tier LLM**
(`FallbackLLMRefiner`, Gemini → Ollama chain — **zero Anthropic quota**). The
referee is the real `cli-judge`.

### 1. automate-your-job — a team lead's standup digest

A repetitive human task: turn one captured day of raw activity (`activity.json`)
into a structured standup digest.

| | grade | score | behavior |
|---|---|---|---|
| **before** (baseline `cli.py`) | **F** | 0.0 | `version --json` crashes; digest is plain text, not JSON |
| **after** (loop-refined) | **A** | 100.0 | `version --json` exits clean; emits one JSON object with `yesterday` / `today` / `blockers`, and the captured "staging DB creds" blocker surfaces under `blockers` |

**Trajectory:** `F → A` (converged, 2 iterations). Proof:
[`demos/targets/standup/PROOF.md`](../demos/targets/standup/PROOF.md).

### 2. factcli — a CLI brought up to the agent-native contract

The project's first genuine end-to-end run: a real referee graded it, a free LLM
improved it, and the convergence policy + rollback worked live.

| | grade | score | failing tasks |
|---|---|---|---|
| **before** (baseline `cli.py`) | **F** | 0.0 | all 3 — crashing `version`, `project new` prompts instead of running non-interactively, `fs ls` missing the `items` key |
| **after** (loop-refined) | **A** | 100.0 | none |

**Trajectory:** `F → F → F → A` (converged, 4 iterations). Note the honesty:
**two refactors were rolled back for no gain**; only the third, which passed all
three contract tasks, was accepted. Proof:
[`demos/targets/factcli/PROOF.md`](../demos/targets/factcli/PROOF.md).

### 3. one-person-industrial-engine — a 2-slice fleet

Not one tool but a **fleet**: an upstream API slice and a dependent daily-digest
slice, converged in dependency order with the upstream outcome routed downstream.

| slice | before | after |
|---|---|---|
| API slice | **F** | **A** |
| daily-digest slice | **F** | **A** |

**Trajectory:** `F → A` on both (converged). Proof:
[`demos/fleets/one-person-industrial-engine/PROOF.md`](../demos/fleets/one-person-industrial-engine/PROOF.md).

---

## 🧪 Illustrative examples (recipes — expected trajectory, not yet a live run)

These show the *shape* of the loop across domains. They are labeled
`illustrative` in `demos/results/*.json` and are **not** recorded live runs — do
not cite them as proof.

| Recipe | before → after | outcome | note |
|---|---|---|---|
| **pr-lifecycle** (autonomous PR-lifecycle CLI) | `C → B → A` | converged | the inner loop under a PR-babysitter outer loop |
| **quant-macro** (Frankfurter FX CLI) | `C → B → A` | converged | a data/API tool climbing to A |
| **software-arch** (microservice ops CLI) | `D → C → B` | **stopped at B** | honest non-A outcome — the loop plateaued and stopped rather than fake a green |

The `software-arch` row is the important one: when the loop can't reach the bar,
it **stops and says so** (`convergence_status: stopped`, final grade B). An honest
❌/B beats a fabricated A.

---

## How to read a run yourself

```bash
loop-anything demo list --json                 # every demo + its source (live_verified | illustrative)
loop-anything demo show automate-your-job      # one demo's detail
loop-anything report <run_id>                  # the research report for a run you drove
loop-anything status                           # your recorded runs
```

Every verified card's before/after grade, trajectory, and evidence files are under
`demos/targets/<id>/` (single) or `demos/fleets/<id>/` (fleet); the recorded
result JSON is `demos/results/<id>.json`.
