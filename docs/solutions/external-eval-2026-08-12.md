# Eval of an external architecture review (2026-08-12)

An external reviewer scored this repo **8.6/10** and proposed 12 upgrades + a 23-item
backlog, headlined by: *"the architecture is too CLI-shaped; add `artifact_type` and
refactor around GoalContract → Artifact → Evaluator → Refiner → Gate → EvidencePack."*

This document is the repo's answer, checked against the **code** rather than the README.

---

## The meta-finding: it is a README review, not a code review

Every citation in the review resolves to `[1] — the GitHub README`. That is not a
disqualifier — the README is the public contract, and a reviewer reading it and
concluding "this is CLI-shaped" is *evidence the README is CLI-shaped*. But it means
the review cannot see the seams that already exist, and three of its twelve proposals
would remove one.

So the review splits cleanly:

| Verdict | Items | Meaning |
|---|---|---|
| **Real gap** | 1, 5, 6, 7, 8, 9 | Genuinely absent. Worth building. |
| **Partial** | 3, 4, 10, 11, 12 | The mechanism exists; the surface or taxonomy is thin. |
| **Already exists** | 2 | Shipped as the `Domain` seam; the proposal would *regress* it. |
| **Reject** | §20 | A big-bang rename of 9k LOC / 599 tests with zero behavior change. |

---

## Item-by-item

### 1. `GoalContract` — **REAL GAP → shipped this turn**

Correct. Run inputs existed only as CLI flags: unreviewable, un-diffable, impossible to
attach to the proof pack the run produces.

Shipped as `src/loopeng/contracts/run_contract.py` — but deliberately **narrower** than
proposed. See [run-contract.md](run-contract.md) for the three rules. The short version:
the proposed schema contains fields nothing would consume (`safety_policy`,
`evaluation_adapter`, per-dimension weights). A declared-but-unenforced field is exactly
the false-green this engine exists to prevent, so the contract **rejects** them at parse
time instead of accepting them decoratively.

### 2. "Split judge into evaluator types" — **ALREADY EXISTS; the proposal regresses it**

The review proposes `Evaluator(Protocol)` + a table mapping artifact → evaluator. That
protocol has been in the tree since plan-004:

- `adapters/base.py` — `Judge` / `Factory` / `Refiner` / `Compounder` / `Checkpoint` protocols
- `domains/base.py` — `Domain` binds *classify → factory → judge* for a target shape
- `domains/registry.py` — `DomainRegistry`, first-match-wins, "a new domain arrives as a
  registration, never as an edit to `router.py` or the controller"
- Concrete referees already registered: `adapters/judge.py` (CLI-Judge),
  `adapters/spec_judge.py`, `adapters/tooling_judge.py`,
  `domains/physical_ai/sim_judge.py`

The proposed `artifact_type: Literal["cli", "mcp_server", "agent_skill", …]` is a
**closed enum in a central contract file**. Adding an artifact type would then require
editing that file — re-centralizing exactly what the open registry decentralized. The
generalization axis here is *registration*, not *enumeration*.

**Accepted correction:** the README does not say this, which is why a careful reader
concluded the opposite. That is a README defect, not an architecture defect.

### 3. Typed recovery taxonomy — **PARTIAL, worth finishing**

Already typed: `loop/convergence.py` emits machine-readable `reason_code` —
`PLATEAU` / `ITERATION_CAP` / `TOKEN_CAP` / `WALL_CAP` — plus terminal `BLOCKED_SAFETY`.
Transient-infra recovery is real too: `Refiner.last_infra_failure` + `Budget.max_tool_retries`
retries *only* the infra class, never a clean no-change or a post-judge safety failure.

Genuinely missing from the taxonomy: `referee_unavailable` (must fail closed),
`adapter_contract`, `human_gate_timeout`. Small, additive, worth doing.

### 4. `EvidencePack` — **PARTIAL; the honest half already works**

`proof.ProofPack.from_run` builds `before_grade` / `after_grade` / `dim_diff` /
`iterations` / `convergence_status` / `elapsed_seconds` / `token_cost` /
`regression_tests` from a real store run, and **omits rather than fakes** any field it
has no source for.

The proposed schema adds fields with no producer (`safety_events`,
`artifact_before/after` snapshots). One is closer than the review knew:
`MemoryStore.record_confirmation` already persists human decisions.

Shipped this turn instead of a bigger schema: `evidence.required` in a contract is
**checked against the real pack** (`loop-anything contract evidence <path> --run N`,
exit 1 on a gap). A promise now has to be met by a run.

### 5. Risk-tiered human gates — **REAL GAP, but the proposed shape is unsafe**

The tiering idea is right. The proposed YAML is not: it makes
`require_confirm_before_ship` a caller-settable boolean, which means a caller can author
`false`. `config.VerificationGate` deliberately has **no caller-settable bypass** — only a
CI-infrastructure env var, and never for `--scheduled` runs.

The contract shipped here therefore makes the gate **monotonic**: `require_human_confirm`
may be omitted or `true`; `false` is a parse error. Tiering should land the same way —
tiers may only *add* reviewers, never remove the base confirmation. Deferred until there
is a real risk signal to classify on; a tier table with no classifier is a knob that only
ever lowers the default.

### 6. Loop-readiness score — **REAL GAP, recommended next**

Nothing grades whether a target is *loopable* before the loop starts. `preflight.py`
detects the four external **tools**; it says nothing about the target's testability,
rollback surface, or machine-readable success criteria. Highest-value remaining item for
adoption, and it composes with the contract shipped here (`readiness --contract`).

### 7. `loop.yaml` — **REAL GAP → shipped this turn** (same unit as #1)

### 8. MCP lane — **REAL GAP, and cheap**

Correct, and cheaper than the review thinks: it is a `Domain` registration + an
`mcp_contract` judge, with no core change (see #2). This is where "anything" genuinely
extends — via the registry, not an enum.

### 9. Benchmark mode + **false-green rate** — **REAL GAP; the best idea in the review**

The single most valuable proposal. "How often does the loop say A when a stronger
evaluator disagrees" is the trust metric this repo lacks. The seed measurement exists —
`probe_grade_variance` / `loop-anything judge-variance` measures referee stability on an
unchanged tool — but nothing yet compares a converged verdict against a stronger judge.

### 10. Ablation as a first-class command — **PARTIAL**

`flywheel/ablation.py` exists and already enforces the honest discipline (an ablation is
`live_verified` only when both legs carry real run ids). What is missing is the CLI verb
and the `--without-rollback` / `--without-safety-gate` legs. Note the last one is
delicate: ablating the safety gate must never be runnable against a real target.

### 11. Lane maturity badges — **MOSTLY EXISTS**

`demos/result.py` carries `source: live_verified | illustrative`, `cli.py` has a single
write path to `live_verified` (only a real recorded run flips it), and
`showcase/generate.py` renders "illustrative — not a verified run". The proposed 5-badge
ladder (`adapter_ready`, `beta`, `research_only`) is a refinement of a discipline already
in place.

### 12. Positioning — **PARTIAL**

`docs/solutions/integrate-loop-engineering.md` already frames outer-loop vs inner-loop.
Adding LangGraph and Codex to that table is a straight improvement.

### §20 proposed directory tree — **REJECT**

A wholesale rename of a 9k-LOC, 599-test engine with no behavior change, on a repo whose
own fitness functions (`tests/test_architecture.py`) pin the current import arrows. The
correct move is the opposite: **make the README describe the architecture that exists**
(the `Domain` seam), and add lanes by registration.

---

## Counter-scorecard (code-based, not README-based)

| Dimension | Review | Here | Why the difference |
|---|--:|--:|---|
| Goal clarity | 8.5 | **8.5 → 9.0** | Agreed; closed this turn by the run contract. |
| Independent evaluation | 9.5 | **9.5** | Agreed. `loop/integrity.py` enforces maker ≠ checker *and* oracle ≠ checker at runner entry. |
| Safety gate | 9.0 | **8.5** | *Lower.* Terminal `BLOCKED_SAFETY` is right, but `gate.yaml`'s denylist is a declared policy, not an enforced one on every write path. |
| Recovery | 8.5 | **8.5** | Agreed — reason codes exist, the taxonomy is incomplete (#3). |
| Human gate | 8.0 | **9.0** | *Higher.* The review missed that there is deliberately no caller-settable bypass, and that `--scheduled --confirm` is rejected. |
| Generality | 7.0 | **8.5** | *Higher.* The `Domain` registry is the generality seam; what is missing is registered lanes, not architecture. |
| Observability | 8.0 | **7.5** | *Lower.* Proof packs are strong; there is no trace schema and no cross-run metric surface (#9). |
| Enterprise readiness | 7.8 | **7.0** | *Lower.* No tenancy, no RBAC, no secrets story, and the false-green rate is unmeasured. |

**Net: the review's headline is wrong (the core is not CLI-shaped), its top-6 backlog is
about half real, and its best idea (#9, false-green rate) it ranks P1 rather than P0.**

---

## What this turn shipped

`run --contract loop.yaml` + `contract check` + `contract evidence` — items 1 and 7,
built so they cannot make items 2 and 5 worse.

## Recommended order for the rest

1. **#9 false-green benchmark** (P0 — it is the trust metric, and everything else is
   easier to trust once it exists)
2. **#6 loop readiness** (adoption; composes with the contract)
3. **#8 MCP lane** (proves "anything" via registration, ~1 domain + 1 judge)
4. **#3 failure taxonomy** + **#10 ablate CLI** (small, additive)
5. **README rewrite** to describe the `Domain` seam — the fix for the meta-finding
6. **#5 risk tiers** — only after a real risk classifier exists
