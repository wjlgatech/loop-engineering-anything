# Agent Loop Engineering — conformance audit

Rubric: `docs/rubrics/archive/agent-loop-engineering.v1.yml` — 26 items drawn from *Agent Loop Engineering — 讲座总结* (DataApplab / AI聘 (info@aipin.io), received 2026-08-20).

That source is a **lecture summary; taxonomy, no verification against a running system**. Every claim below is scored against shipped code or a test that was actually executed. No evidence means no.

**Conformance: 23/23 (100%)** verifiable claims implemented · 3 declared gaps · 0 unmeasured · gate **PASS**

## Implemented — with observed evidence

- **L1-loop-not-oneshot** · 2 — why an agent needs a loop
  - claim: The system iterates plan→act→observe→evaluate rather than answering once.
  - evidence: `src/loopeng/loop/controller.py:75`
- **L2-goal** · 3 — Goal
  - claim: The loop carries an explicit goal and a definition of done.
  - evidence: `src/loopeng/config.py:89`
- **L3-state** · 3 — State
  - claim: Progress lives outside the model: steps taken, results, environment.
  - evidence: `src/loopeng/memory/store.py:196`
- **L4-policy** · 3 — Policy
  - claim: Something decides the next action from the current state.
  - evidence: `src/loopeng/adapters/base.py:103`
- **L5-action-space** · 3 — Action space
  - claim: The agent's available actions are declared, not open-ended.
  - evidence: `src/loopeng/adapters/base.py:52`
- **L6-observation** · 3 — Observation
  - claim: Every action returns structured environment feedback.
  - evidence: `src/loopeng/adapters/base.py:16`
- **L7-evaluation** · 3/10 — Evaluation is the controller
  - claim: A verifiable evaluator decides progress, not the maker's self-report.
  - evidence: `src/loopeng/adapters/base.py:62`
- **L8-maker-not-checker** · 10 — evaluation must be trustworthy
  - claim: The thing that builds is not the thing that grades.
  - evidence: `tests/test_maker_checker.py -> 30 passed in 0.14s`
- **L9-reflection** · 4/6 — Plan-Execute-Observe-Reflect, Self-Reflection
  - claim: Why the last attempt scored what it did is carried into the next attempt.
  - evidence: `src/loopeng/adapters/base.py:66`
- **L10-replan-on-plateau** · 4 — the plan is not immutable
  - claim: Feedback can force a change of strategy, not just another attempt.
  - evidence: `src/loopeng/config.py:100`
- **L11-retry-transient-only** · 8 — Retry vs Recovery
  - claim: Only retryable (infrastructure) failures are retried; not every error.
  - evidence: `src/loopeng/adapters/base.py:142`
- **L12-recovery-state** · 8 — Recovery keeps enough state to resume
  - claim: A failed change can be rolled back rather than restarting from zero.
  - evidence: `tests/test_checkpoint.py -> 2 passed in 0.49s`
- **L13-exit-success** · 9 — explicit exits: success
  - claim: The loop stops when the goal is verifiably met.
  - evidence: `src/loopeng/loop/convergence.py:29`
- **L14-exit-budget** · 9/14 — explicit exits: budget (iterations, tokens, wall clock)
  - claim: The loop stops on a spent budget, and the budget has more than one dimension.
  - evidence: `src/loopeng/loop/convergence.py:38`
- **L15-exit-giveup** · 9 — explicit exits: give up and report
  - claim: Repeated non-progress ends the run and reports failure instead of looping.
  - evidence: `src/loopeng/loop/convergence.py:36`
- **L16-safety-terminal** · 13 — permission control
  - claim: A safety failure is terminal and unbypassable, whatever the score.
  - evidence: `src/loopeng/loop/convergence.py:30`
- **L17-permission-boundary** · 13 — which tools/data the agent may touch is limited
  - claim: Execution is jailed and shell metacharacters are refused.
  - evidence: `src/loopeng/adapters/safety.py:5`
- **L18-human-in-the-loop** · 12 — Human-in-the-Loop for high-risk actions
  - claim: High-risk completion requires a human, and the caller cannot self-approve.
  - evidence: `src/loopeng/config.py:127`
- **L19-hitl-unbypassable** · 12 — the gate must actually hold
  - claim: An unattended run cannot pre-confirm its own result.
  - evidence: `tests/test_run_contract.py::test_contract_can_never_disable_the_human_gate -> 4 passed in 0.05s`
- **L20-multi-agent-graph** · 11 — Loop becomes Graph with many agents
  - claim: Multiple agents are coordinated as a dependency graph, cycles refused.
  - evidence: `src/loopeng/orchestration/coordinator.py:6`
- **L21-observability** · 13 — every iteration leaves enough log/trace to debug
  - claim: A run is reconstructable after the fact from recorded evidence.
  - evidence: `src/loopeng/autonomous/report.py:37`
- **L22-token-accounting** · 14 — Token economics: measure tokens, time, iterations, success
  - claim: Token cost, wall time and iteration count are recorded per run.
  - evidence: `src/loopeng/proof.py:108`
- **L23-cost-never-faked** · 14 — measurement must be real to be useful
  - claim: An unavailable cost is omitted, never estimated into the record.
  - evidence: `tests/test_proof.py -> 7 passed in 0.09s`

## Declared gaps — the engine does NOT do these, and says so

Each probe passes while the gap is real and fails the moment it silently closes, so this list cannot quietly go stale.

- **L24-typed-failure-taxonomy** · 8 — classify the error before choosing a response
  - claim: Failures are classified into a named taxonomy (referee-unavailable, adapter-contract, human-gate-timeout).
  - status: **confirmed absent** — Only infra-vs-clean is distinguished. External eval item 3.
- **L25-branching-search** · 7 — Tree of Thoughts
  - claim: The loop explores multiple candidate paths and prunes them.
  - status: **confirmed absent** — Single-path refine with a dimension pivot. Deliberate: branching multiplies cost.
- **L26-trace-schema** · 13 — observability as a first-class trace
  - claim: Runs emit a structured trace (spans/trace ids), not just a report.
  - status: **confirmed absent** — Reports and proof packs exist; a span-level trace schema does not.

