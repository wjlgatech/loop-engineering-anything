# Three deliberate non-gaps vs the generic agent loop

A gap analysis (`docs/plans/2026-06-16-005-feat-loop-engineering-gap-bridges-plan.md`)
compared this loop against the generic agent-loop anatomy popularized as "Loop
Engineering" (state → reason → act → observe → reflect → terminate, plus a ladder
to multi-agent loops). Most of that anatomy we either meet or exceed. Three
apparent "gaps" are **deliberate design choices**, not omissions. Each is named
here with the failure mode the generic framework worries about and the concrete
reason our design tolerates or mitigates it — a choice with a stated cost is
defensible; a bare label is not.

## 1. Outer-loop sovereignty — we referee output, not inner tokens

**Choice.** Our controller governs the *outer* loop (route → generate → judge →
refactor → re-judge → compound). The refiner's own inner think-act-observe (e.g.
`/ce-work`) is a swappable vendor behind the `Refiner` protocol; we grade its
*output*, never its tokens. `controller.py` never introspects refiner internals.

**Failure mode it forgoes.** We cannot reflect on or correct the inner agent's
reasoning mid-step.

**Why it's acceptable.** The inner loop is interchangeable (`ClaudeCodeRefiner`
vs `FallbackLLMRefiner`) precisely because we don't couple to its internals
(KTD1 wrap-don't-fork). Instrumenting the inner loop would break that boundary
and turn an upstream tool into a fork. We are the meta-loop any agent loop plugs
into — that is the thesis, not a shortcoming.

## 2. Single referee of record — quality comes only from CLI-Judge

**Choice.** Convergence and acceptance read exactly one quality signal: the
`Verdict` from a maker-distinct judge (`convergence.py`, KTD4). The post wants
rich multi-source observation/reflection.

**Failure mode it forgoes.** A single referee is a single point of
calibration failure.

**Why it's acceptable.** The multi-signal richness lives *inside* the judge's 5
dimensions + safety gate, not across multiple quality authorities. Admitting a
second quality source (the refiner's self-report, an inner-confidence score)
would let a maker influence its own grade — `integrity.py` fails closed if
`refiner is judge` (R10). The constraint is the maker≠checker moat. Calibration
drift over time is a *known, separately-addressable* concern: the
`judge-variance` probe checks determinism, and held-out seeds bound referee
gaming (`docs/solutions/p0-feasibility-gates.md`); a longitudinal drift detector
is deferred follow-up, not a hole in this design.

## 3. Gated human confirm — anti-cognitive-surrender by default

**Choice.** Human confirmation gates *shipping* (not mid-loop iteration). The
`VerificationGate` is ON by default, has no caller-settable bypass, and scheduled
runs stay confirm-required regardless of `CI` (`config.py`, `integrity.py`). The
post lists "human escalation" as one control among many.

**Failure mode it forgoes.** Fully autonomous shipping (no human in the loop at
all).

**Why it's acceptable.** A `CONVERGED` result is a *claim* until confirmed — the
gate defeats a reward-hacked maker that declares victory. U5 makes the gate
*legible* (`describe_gate_reason` surfaces the borderline grade/score/dimension)
and records the human's verdict to a write-only `confirmations` audit table, so
the human makes an informed decision rather than rubber-stamping — and a recorded
approval can never become an auto-ship (KTD5).

See the plan above and `docs/solutions/p0-feasibility-gates.md`.
