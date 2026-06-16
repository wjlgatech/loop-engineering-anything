# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- **Flaky `test_concurrent_sqlite_writes_do_not_corrupt` (concurrent git-worktree
  race).** `git worktree add`/`remove`/`prune` mutate shared `.git/worktrees/`
  metadata and are not concurrency-safe against one repo — racing fan-out
  intermittently failed CI with `failed to read .git/worktrees/<x>/commondir`.
  `autonomous/parallel.py` now serializes worktree *creation/teardown* through a
  module lock (`_WORKTREE_LOCK`) while each loop's `run` still executes fully in
  parallel. Stress-verified 12/12 green (previously intermittent).

### Added
- **`automate-your-job` graduated from recipe → live `live_verified` demo** — the
  first recipe to become a real, recorded run. A team-lead's repetitive task
  (turn a captured day of activity into a standup digest) was handed to the loop:
  the real `cli-judge` referee graded it against the **captured task payload**
  (`demos/targets/standup/activity.json`) and the free-tier `FallbackLLMRefiner`
  (Gemini, no Anthropic) refactored the buggy CLI **F(0) → A(100)**, trajectory
  `F → A`, converged in 2 iterations. Recorded via `loop-anything demo record`
  (the only path to `live_verified`, KTD2). Ships the runnable target
  (`demos/targets/standup/`), adapter (`demos/adapters/automate-your-job.py`),
  suite + captured-payload task (`demos/suites/`), result + report
  (`demos/results/automate-your-job.*`), and `PROOF.md`. The hub now shows its
  first **verified-run** card (14 demos / 6 recipes). New cohort recognized in
  `tests/test_starter_demos.py` (the 10 article starters still ship illustrative).
- **Two agency-themed loop recipes in the hub** — from an external AI-agency
  brainstorm, kept only the ideas that actually map to a loop engine (the rest
  were consumer/psych products, off-identity): `demos/automate-your-job.yaml` +
  `docs/recipes/automate-your-job.md` (point the loop at your own repetitive
  role and own the automation — literally what the engine does, graded against
  your real task payloads) and `demos/one-person-industrial-engine.yaml` +
  `docs/recipes/one-person-industrial-engine.md` (a coordinated fleet of loops,
  one per product slice — depends on the plan-006 fleet layer). Shipped honestly
  as **recipes** (not fake demos), so they appear in the hub's recipes lane
  badged not-runnable-yet. Hub now lists 7 recipes; 20 manifests validate.
- **First real end-to-end live proof (F → A) — the refine frontier, validated.**
  A self-contained proof target (`demos/targets/factcli/`) + CLI-Judge adapter
  (`demos/adapters/factcli.py`) + a three-task D2 suite (`demos/suites/proof.yaml`),
  driven by the real `LoopController` with the real `cli-judge` referee and the
  free-tier `FallbackLLMRefiner` (Gemini → Ollama, **no Anthropic quota**). The
  loop refactored a deliberately-buggy CLI from **grade F (0)** to **grade A
  (100)** — trajectory `F → F → F → A`, converged in 4 iterations, with two
  no-gain refactors rolled back live. Evidence + reproduction in
  `demos/targets/factcli/PROOF.md`. Needs no external catalog tool or Go
  toolchain. Next: wire it as a recorded `live_verified` hub card via `demo record`.

### Changed
- **loop-anything-hub redesign (dogfooded)** — restyled the self-contained
  showcase generator (`src/loopeng/showcase/generate.py`) toward the flat,
  type-led, generous-whitespace pattern of [printingpress.dev](https://printingpress.dev):
  light canvas with one restrained accent (and a `prefers-color-scheme: dark`
  variant as the 10×), a sticky top nav, an eyebrow + stronger hero hierarchy,
  flat bordered cards with subtle hover, pill domain tags, soft-tint badge pills,
  and a monospace grade trajectory. We dogfooded our own loop: printingpress.dev's
  pattern was the **judge** (`docs/solutions/showcase-design-rubric.md`), the CSS
  rewrite was the refactor, and before/after screenshots were the re-judge —
  graded **C → A** on design while holding the two hard gates (self-containment,
  context-aware escaping) and all 13 showcase tests.

### Fixed
- **U3 retry was dead for `FallbackLLMRefiner`** (follow-up to plan
  `docs/plans/2026-06-16-005-...`, found in code review): the claude-free refiner
  never set `last_infra_failure`, so a fully-throttled provider chain (the exact
  transient case U3's retry was built for) was treated as a clean no-change and
  rolled back instead of retried. Fix: `FallbackLLMRefiner` now sets
  `last_infra_failure = (content is None)` — `True` only when the whole chain
  failed, `False` when a provider answered (even with no usable edits). The
  attribute is now declared on the `Refiner` protocol alongside `last_token_cost`
  so the retry contract is complete. Tests in `tests/test_llm_refiner.py`.

### Changed
- **Fleet coordinator cleanup (post-code-review, non-behavioral)**: extracted a
  shared `apply_item_result` so the coordinator's wave loop and
  `escalation.rebrief_item` map a result identically (recording the outcome
  *before* flipping status to converged, closing the converged-without-outcome
  window); the coordinator now reads `fleet_items` once per wave and passes that
  snapshot to `gather_upstream_outcomes` (no per-item re-read); added a test
  asserting the `schema.sql` status DEFAULTs match the `FleetItemStatus` /
  `FleetRunStatus` enum values.

### Added
- **Fleet orchestration layer, Phase A — U6: boundary docs** (same plan):
  **`docs/solutions/fleet-orchestration-boundary.md`** (new) names the
  loop-engine-not-Agent-IDE boundary vs. Agent Orchestrator (same orchestration
  pattern, different worker substrate; enforced by the runner contract), the
  failure mode it accepts, and the fleet-level invariants. `AGENTS.md` gains an
  `orchestration/` layout row + a boundary entry; `README.md` gains a "Fleets"
  subsection.
- **Fleet orchestration layer, Phase A — U1: lifecycle state + persistence**
  (plan `docs/plans/2026-06-16-006-feat-fleet-orchestration-layer-plan.md`): the
  foundation for coordinating multiple self-improving loops under one goal.
  - **`src/loopeng/memory/fleet_state.py`** (new): `FleetItemStatus` /
    `FleetRunStatus` enums + a fail-closed legal-transition guard
    (`assert_item_transition`) mirroring the controller's `LoopState`, plus
    `FleetItem` / `FleetRun` dataclasses. Pure data, no IO — lives in `memory/`
    so the store enforces the guard without a layering cycle.
  - **`src/loopeng/memory/schema.sql`** + **`store.py`**: new `fleet_runs` /
    `fleet_items` tables (`CREATE TABLE IF NOT EXISTS`) + `create_fleet`,
    `set_fleet_status`, `add_fleet_item`, `set_item_status` (guard-enforced),
    `record_item_outcome`, `fleet_items`, `escalations`, `get_fleet`.
  - Tests: `tests/test_fleet_state.py` (new) + fleet persistence in
    `tests/test_memory_store.py`.
- **Fleet orchestration layer, Phase A — U2: dependency-ordered coordinator**
  (same plan): **`src/loopeng/orchestration/coordinator.py`** (new) runs fleet
  items in topological waves over the existing `run_parallel` fan-out — ready
  items dispatched together, dependents unlocked as upstreams converge. Cycles
  and dangling edges fail closed before any worktree is created (Kahn's
  algorithm); a non-converged dependency marks dependents `blocked_on_dep`; an
  all-escalated/no-ready state ends the fleet `awaiting_human` (resumable, never a
  hang). Thin `classify` (U4) and `route` (U3) seams are pre-wired. Tests:
  `tests/test_fleet_coordinator.py` (new) — flat fan-out characterization,
  diamond-DAG ordering, cycle rejection, blocked-on-dep, fleet PARK.
- **Fleet orchestration layer, Phase A — U3: automatic feedback routing**
  (same plan): a completed item's outcome is routed into its dependents' briefs,
  deterministically (no LLM). Built the brief-injection seam the doc-review flagged
  as missing: an additive, backward-compatible `upstream_context` parameter on
  `run_loop` / `run_refine_loop` → `LoopController` → a new advisory
  `RefactorBrief.upstream_outcomes` field (distinct from `recurring_failures`:
  caller-injected structured cross-item outcomes vs. store-derived fixture
  strings). The `ClaudeCodeRefiner` prompt surfaces it. The coordinator *pulls*
  each item's dependencies' recorded outcomes before dispatch
  (`src/loopeng/orchestration/routing.py`, new). Absent the parameter, behavior is
  identical to before. Tests: `tests/test_fleet_routing.py` (new), brief field in
  `tests/test_refactor_brief.py`, controller threading in
  `tests/test_loop_controller.py`, end-to-end in `tests/test_fleet_coordinator.py`.
- **Fleet orchestration layer, Phase A — U4: human-efficiency escalation**
  (same plan): **`src/loopeng/orchestration/escalation.py`** (new). Only
  high-judgment forks reach a human — `classify_with_escalation` sends a
  `BLOCKED_SAFETY`, converged-but-gated, or stuck item to the escalation queue
  while a clean converged-and-shippable item auto-proceeds; the fleet never
  auto-merges a blocked/unconfirmed item (`RunResult.shippable` is the sole
  authority, R10 lifted to the fleet). `rebrief_item` re-runs a single escalated
  worker with a human note added to its brief context, updating the existing item
  row in place. Tests: `tests/test_fleet_escalation.py` (new).
- **Fleet orchestration layer, Phase A — U5: fleet CLI + report** (same plan):
  a `loop-anything fleet` command group (`run` / `status` / `report` /
  `escalations`). **`src/loopeng/orchestration/spec.py`** (new) parses + validates
  a hand-authored fleet spec (rejects dangling deps before any row is created) and
  materializes the fleet; **`src/loopeng/orchestration/fleet_report.py`** (new)
  aggregates per-item lifecycle/grade/escalations (keeping `autonomous/report.py`
  the untouched per-run building block). `fleet run` materializes the fleet and
  is honest that live per-item execution needs the factory adapters (same gate as
  `run`); the coordinator is exercised in tests. Tests: `tests/test_fleet_cli.py`
  (new).
- **Loop-engineering gap-bridges, U6 — name the three deliberate non-gaps**
  (same plan): documents outer-loop sovereignty, single referee of record, and
  the gated human-confirm posture as design choices (each with the failure mode
  it accepts and why), so contributors and agents don't "fix" them.
  - **`docs/solutions/outer-loop-non-gaps.md`** (new) — the decision record.
  - **`AGENTS.md`** — a boundaries entry naming the three; **`README.md`** — a
    "Where this differs from a generic agent loop" subsection.
- **Loop-engineering gap-bridges, U1 — cross-run recurring-failure memory in the
  refactor brief** (plan `docs/plans/2026-06-16-005-feat-loop-engineering-gap-bridges-plan.md`):
  the loop now starts each run knowing which fixtures defeated prior runs *of the
  same target*, realizing the post's "memory" pillar at the loop-control level.
  Why: `recurring_failures()` existed but was called only in tests; briefs were
  built from the current verdict alone.
  - **`src/loopeng/memory/store.py`**: `recurring_failures(min_runs=2, *, target=None)`
    gains a target-scoped variant (join through `runs.target`) so one target's
    history never leaks into an unrelated target's brief. The unscoped form is
    unchanged (transcendent reporting).
  - **`src/loopeng/loop/refactor_brief.py`** + **`adapters/base.py`**:
    `build_refactor_brief(verdict, goal, recurring_failures=None)` intersects
    history with the current verdict's failing set — only fixtures that recur
    *and* fail now are re-prioritized; recurring-but-passing fixtures ride along
    in a new advisory `RefactorBrief.recurring_failures` field. Live signal is
    never demoted below stale history.
  - **`src/loopeng/loop/controller.py`** fetches the target-scoped history once
    per run and threads it into the brief; **`adapters/compound_engineering.py`**
    surfaces it in the `/ce-work` prompt as lower-priority watch-for-regression
    context.
  - Tests: `tests/test_refactor_brief.py` (new), target-scoping in
    `tests/test_memory_store.py`, brief-injection in `tests/test_loop_controller.py`.
- **Loop-engineering gap-bridges, U4 — enforceable cost budget** (same plan):
  fixes a latent bug where `tokens_spent` was initialized to `0` and never
  updated, so the token budget gate always compared against `0` and never fired.
  - **`src/loopeng/adapters/base.py`**: `Refiner` protocol gains an optional
    `last_token_cost: int | None`; the controller reads it protocol-bound (never
    reaching into a concrete refiner). `FallbackLLMRefiner` declares it `None`.
  - **`src/loopeng/loop/controller.py`** threads each refactor's reported cost
    into `tokens_spent` and `record_iteration(token_cost=...)`, captures a
    monotonic start time, and passes elapsed seconds into `convergence.evaluate`.
    Warns once when a `token_budget` is set against a refiner that reports no cost.
  - **`src/loopeng/loop/convergence.py`**: `evaluate` gains a wall-clock terminal
    predicate (time passed in, so it stays pure). **`config.py`** adds
    `Budget.max_wall_seconds` (universal cost backstop) and rewrites the
    `token_budget` docstring to state enforcement is conditional on cost reporting.
  - Tests: wall-clock + token paths in `tests/test_convergence.py`; token
    threading, no-cost warning, and wall-clock termination in
    `tests/test_loop_controller.py`.
- **Loop-engineering gap-bridges, U3 — infra-failure vs quality-regression
  retry** (same plan): a transient tool failure (timeout / non-zero exit /
  missing executable) is now retried with bounded backoff instead of being
  mistaken for a quality regression; a clean no-change result and a post-judge
  safety failure are never retried.
  - **`src/loopeng/adapters/safety.py`**: `is_infra_failure(ProcResult)` classifier.
  - **`src/loopeng/adapters/compound_engineering.py`**: `ClaudeCodeRefiner`
    sets `last_infra_failure` (True only on infra failure, False on a clean
    no-change result) — classification stays in the concrete refiner, not the
    `Refiner` protocol.
  - **`src/loopeng/loop/controller.py`**: `_refactor_with_retry` retries only the
    infra class with exponential backoff (`Budget.max_tool_retries`, default 2),
    via an injectable `sleeper`. Retries do not increment the iteration count;
    wall time is bounded by `max_wall_seconds`. Safety is detected post-judge,
    downstream of retry, so it is never retried.
  - Tests: classifier + flag in `tests/test_compound_engineering.py`;
    retry-recovers / bounded-exhaustion / safety-never-retried in
    `tests/test_loop_controller.py`.
- **Loop-engineering gap-bridges, U2 — plateau triggers a strategy pivot**
  (same plan): on a plateau the loop now rotates to the next-lowest dimension
  once (per `Budget.plateau_pivots`, default 1) before stopping, instead of
  terminating immediately.
  - **`src/loopeng/loop/convergence.py`**: `Decision` gains a structured
    `reason_code` (`plateau` / `iteration_cap` / `token_cap` / `wall_cap`) so the
    controller pivots only on a *sole* plateau — a cap stop always wins.
  - **`src/loopeng/memory/store.py`**: `is_plateaued(since_iteration=...)` scopes
    the no-gain test to post-pivot iterations, giving a freshly-pivoted strategy
    a clean window.
  - **`src/loopeng/loop/refactor_brief.py`**: `build_refactor_brief(exclude_dims=...)`
    demotes already-tried dimensions to the back so the brief rotates.
  - **`src/loopeng/loop/controller.py`**: tracks pivot state, intercepts the
    plateau→STOPPED transition while pivots remain, excludes the hammered dims,
    and resets the plateau window. `convergence.evaluate` stays a pure function.
    **`config.py`** adds `Budget.plateau_pivots`.
  - Tests: `since_iteration` in `tests/test_memory_store.py`, `exclude_dims` in
    `tests/test_refactor_brief.py`, `reason_code` in `tests/test_convergence.py`,
    pivot / cap-wins / `plateau_pivots=0` characterization in
    `tests/test_loop_controller.py`.
- **Loop-engineering gap-bridges, U5 — legible human-confirm gate + recorded
  verdict** (same plan): when the verification gate requires confirmation, the
  loop now surfaces *why* it fired and records the human's verdict for audit.
  - **`src/loopeng/loop/integrity.py`**: `describe_gate_reason(grade, score, dims)`
    composes a legible reason naming the converged grade/score and the lowest
    dimension. **`controller.py`** `LoopOutcome` carries `score`/`dims` so the
    runner composes the reason without re-judging.
  - **`src/loopeng/memory/schema.sql`** + **`store.py`**: a new `confirmations`
    table (`CREATE TABLE IF NOT EXISTS`) + `record_confirmation` / `confirmations`
    reader. The table is write-only with respect to shippability — nothing reads
    it back into the gate's `confirmed` input (KTD5).
  - **`src/loopeng/autonomous/runner.py`**: `RunResult.gate_reason` surfaces the
    firing reason; `_apply_gate` records the verdict only when confirmation was
    owed. `confirm_convergence` stays the sole shippability authority.
  - Tests: recording + reader in `tests/test_memory_store.py`; gate legibility,
    approve/reject recording, CI-bypass-records-nothing, and write-only-does-not-
    affect-shippability in `tests/test_maker_checker.py`.
- **Loop-engine domain generalization, Phase B — U12: SimJudge referee +
  CMDP safety profile** (plan `docs/plans/2026-06-15-004-...`): the physical-AI-in-sim
  referee that runs a control policy in simulation over a *held-out* seed set
  and returns a normalized `Verdict` (R4/R5/R6/R12). Why: this is the third
  domain that proves the loop spine is substrate-agnostic — a non-software
  artifact graded by a real referee with a real safety gate.
  - **`src/loopeng/domains/physical_ai/sim_judge.py`** (new): `SimJudge.judge(policy_path)`
    averages per-seed reward → `score`, bands it to a non-null `grade` letter
    (KTD1), and derives `safety_ok` from accumulated CMDP cost. **Held-out seeds
    are derived at judge-time from a secret PRG seed** held only in the judge's
    environment (KTD6/R6) and exclude the maker's `dev_seeds`, so the maker
    cannot read or overfit the eval set. NaN reward → safe failure (grade `F`,
    `safety_ok=False`, recorded honestly); empty rollout set → `ValueError`,
    never a fabricated score. `load_simulator()` is a gated dependency
    (skip-not-fail via `SimulatorUnavailable`); the live MuJoCo binding lands in U13.
  - **`src/loopeng/domains/physical_ai/safety_profile.py`** (new): centralized
    `derive_safety_ok(cost, threshold)` (one function, KTD2) — a trip on *any*
    CMDP channel (joint-limit/velocity/torque/collision) or a NaN cost fails
    closed. All reporting is bound to "sim performance only" (R12) — no transfer
    or real-world correctness claim.
  - **`tests/test_sim_judge.py`** (new, 13 tests) exercises the referee against
    *recorded* rollouts (no live sim in the default suite): safety trips,
    held-out/dev-seed disjointness, mean-reward scoring + variance, NaN/empty
    edges, and judge determinism.
- **Loop-engine domain generalization, Phase C — U17: maker/checker contract +
  anti-cognitive-surrender gates** (plan `docs/plans/2026-06-15-004-...`): make
  "maker ≠ checker" an *enforced* precondition and add the verification gate
  unattended loops demand (R6/R10, KTD6). Why: a maker that referees its own
  work, or is graded on seeds it trained on, can silently reward-hack — these
  must fail closed *before* a loop runs.
  - **`src/loopeng/loop/integrity.py`** (new): `assert_loop_integrity` (the
    single preflight call) plus `assert_maker_distinct_from_checker` (refiner
    and judge must be distinct *objects*, by identity), `assert_referee_immutable_to_maker`
    (rejects a wiring where a referee path lives inside the maker's declared
    write surface — the contract-level model of KTD6's filesystem boundary),
    and `assert_heldout_disjoint` (dev seeds vs held-out seeds must not overlap,
    and the held-out set may not be empty). All raise `IntegrityError`
    fail-closed with *names, not values* (mirrors the credential gate).
  - **Human-confirm verification gate** (`config.VerificationGate`, default in
    `Config.gate`): a `CONVERGED` outcome is a *claim* until confirmed. Gate is
    **ON by default**. **Bypass is access-controlled (security finding):** there
    is no caller-settable bypass flag; the only bypass keys on a CI-infrastructure
    env var (`CI`, attended runs only); **scheduled/unattended runs default to
    confirm-required regardless of CI** — a scheduler that sets `CI=true` cannot
    auto-ship a reward-hacked result. `RunResult.shippable` reports the gate's
    verdict (`gate_requires_confirmation` / `confirm_convergence` in
    `loop/integrity.py`).
  - **Runner hook** (`autonomous/runner.py`): `run_loop` / `run_refine_loop`
    call `assert_loop_integrity` before any work (after `validate_target`,
    alongside the credential gate) and gate the `CONVERGED` outcome via new
    `scheduled` / `confirmed` params + optional `referee_paths` /
    `maker_write_paths` / `dev_seeds` / `heldout_seeds` integrity inputs.
  - Tests: `tests/test_maker_checker.py` (new) — same-object maker/checker
    rejected before any run, held-out overlap/empty rejected, referee
    immutability at the contract level, and the full CI-vs-scheduled gate
    matrix through the runner. Existing `test_autonomous_runner.py` stays green.
- **Loop-engine domain generalization, Phase A — U9** (plan
  `docs/plans/2026-06-15-004-feat-loop-engine-domain-generalization-plan.md`):
  widen the loop's contracts so a target can be *any* domain, not just code,
  with **no new states or branches in `loop/controller.py`** (KTD1).
  - **`Domain` plugin protocol** (`src/loopeng/domains/base.py`, new): binds a
    target shape to its adapters via `classify`/`name`/`dependencies`,
    `factory() -> Factory | None` (`None` = refine-only adopt-as-baseline, KTD5),
    and `judge() -> Judge`. The cross-domain safety signal stays on
    `Verdict.safety_ok` (the judge owns per-domain derivation, KTD2), so it is
    not a separate accessor. Imports only the adapter protocols — never the
    controller.
  - **Persisted `score`** (`memory/schema.sql`, `memory/store.py`): `iterations`
    gains a nullable `score REAL` column (additive + idempotent migration for
    pre-existing DBs), threaded through `record_iteration`/`Iteration` and from
    the controller's `_record`. `grade` stays `NOT NULL` — every domain projects
    its native signal onto **both** `score` (primary) and a coarse `grade`
    letter, so the controller, `LoopOutcome`, and the NOT-NULL schema are
    untouched. Legacy `score=NULL` rows still read.
  - `Verdict` docstring clarified: `score` is the primary continuous
    cross-domain signal, `grade` the coarse projection (no shape change,
    back-compatible).
  - Tests: `tests/test_contracts_generalization.py`,
    `tests/test_domain_protocol.py` (R1/R2/R11 — software loop unregressed).
- **Loop-engine domain generalization, Phase A — U10** (same plan):
  score-based convergence + per-domain variance band, so a domain can converge
  on a continuous **score target** with noise handling (R3/R6).
  - **`Budget.target_score: float | None`** (`config.py`): when set, convergence
    and acceptance decide on the score; when `None`, the letter path is
    unchanged.
  - **`convergence.evaluate`** (`loop/convergence.py`): the unbypassable
    `safety_ok=False → BLOCKED_SAFETY` check stays first; then a score target
    converges on `score >= target_score` and **skips the letter ladder
    entirely**; otherwise the existing `grade_rank` path runs unchanged
    (structural ordering, KTD4).
  - **`convergence.is_improvement`**: under a score target, keep/rollback is
    decided on the **score delta vs `min_score_gain`** (not the letter), so a
    real gain/regression inside one letter band is not masked.
  - **Score-aware plateau** (`memory/store.py`): new `score_trajectory`;
    `is_plateaued(..., on_score=True)` ranks the persisted `score` column (falls
    back to grades if any score is unrecorded). The controller passes
    `on_score` only when a score target is set, so the software letter-plateau
    behavior is byte-identical (R2). The "flying turd" guard is otherwise
    untouched.
  - **Variance probe** (`adapters/judge.py`): `probe_grade_variance` documented
    as the multi-seed measurement a stochastic score referee needs — it must run
    with `min_score_gain ≥ recommended_min_score_gain` (> 0).
  - Tests: `tests/test_score_convergence.py` (new) + `tests/test_convergence.py`
    regression pins stay green.
- **Loop-engine domain generalization, Phase A — U11** (same plan):
  domain registry supersedes the router's hard-coded lane heuristics; the two
  software lanes become registered domains with identical behavior (R2/R11).
  - **`DomainRegistry`** (`domains/registry.py`, new): `resolve(target, forced=)`
    asks each registered domain `classify(target)`; a `forced` name overrides;
    an unmatched target raises listing the registered domains. `REGISTRY` is the
    default instance the router shim + runner resolve against. A new domain
    arrives as a `register()` call — never a `router.py`/controller edit.
  - **Software domains** (`domains/software.py`, new): `software-service`
    (Printing-Press) and `software-codebase` (CLI-Anything), both refereed by
    CLI-Judge. The precedence logic (local path > spec > URL) is extracted into
    one reason-carrying `classify_software` so the router shim and each domain's
    `classify` cannot drift. Factory/Judge instances stay injected at the runner
    boundary; the domain names the binding (`lane`/`factory_key`), not the
    instance.
  - **`router.route`** (`router.py`): now a thin compatibility shim — handles the
    forced-lane path, delegates classification to `REGISTRY.resolve`, and adapts
    the resolved software domain back into the legacy `LaneDecision`. Public API
    and the actionable `--lane` error message are unchanged; all of
    `tests/test_router.py` stays green.
  - Tests: `tests/test_domain_registry.py` (new).
- **Loop-engine generalization, Phase C — U14 (scheduler/heartbeat)** (same
  plan): turns the one-off runner into a recurring cadence — Loop Engineering's
  first primitive (R7).
  - **`Heartbeat`** (`src/loopeng/scheduler/heartbeat.py`, new): a runner-agnostic
    cadence engine. `schedule()` registers a target+interval; `tick(now)` fires
    every due target once via an **injected runner** (`ScheduledFire → run_id`),
    honors the interval, isolates a failing run from its siblings (stamps the
    attempt, keeps the prior resume anchor, continues), and resumes from the last
    recorded run via a stable per-target workspace + `resume_run_id`. Optional,
    injected, cadence-driven — wired like the History Compression compressor, no
    new controller state (KTD7).
  - **Durable schedule state** (`memory/schema.sql`, `memory/store.py`): new
    `schedule_state` table (created additively) + `upsert_schedule` /
    `schedules` / `remove_schedule` / `mark_scheduled_fired`, so a registered
    cadence survives a process restart. `last_run_id` is an advisory resume
    anchor (not an enforced FK — keeps the engine decoupled from run creation).
  - **`loop-anything schedule` CLI** (`cli.py`): `add` / `list` / `remove` /
    `tick`. `tick` reports the targets due now (live execution rides the same
    injected runner as the autonomous loop, gated like `run`).
  - Tests: `tests/test_scheduler.py` (new).
- **Loop-engine generalization, Phase C — U15 (connector/actuator layer)** (same
  plan): gives loops a surface to *act* on external systems behind the
  install/credential isolation boundary — the prerequisite for the org/individual
  rungs (R8). _Why:_ a self-improving loop must be able to take real-world actions
  without becoming a path for a generated/refined tool to exfiltrate ambient
  credentials or reach a shell.
  - **`Connector` protocol + isolation boundary** (`src/loopeng/connectors/base.py`,
    new): declared `capabilities` + a structured `act(payload)` surface (payloads
    are dicts, **never shell-interpolated**). `install_connector` mirrors the
    catalog adopter's KTD8 discipline — installs into a throwaway `--target`
    **outside the repo worktree**, **full 40-char SHA pin** (tags/branches
    rejected), `run_tool` (`shell=False`, args list), and a credential gate that
    fails fast by **name** only (`check_credentials`, never a value).
  - **`minimal_env` allowlist** (`src/loopeng/adapters/safety.py`): a *strict
    allowlist* env builder (only `PATH`/`HOME`/... + explicitly passed names),
    complementing the existing `run_tool(env=)` param and `adopt.pruned_env`
    denylist — so a connector child inherits zero ambient secrets by default.
  - **Reference connector** (`src/loopeng/connectors/reference_connector.py`, new):
    a structured-payload "file report" actuator demonstrating the surface; tests
    round-trip the payload in-process (no network, KTD9 skip-not-fail).
  - Tests: `tests/test_connectors.py` (new, 14 cases).
- **Loop-engine generalization, Phase C — U16 (worktree parallelism)** (same
  plan): run multiple loops/targets concurrently in isolated git worktrees
  without file or git collisions (R9).
  - **`run_parallel` fan-out** (`src/loopeng/autonomous/parallel.py`, new):
    single responsibility — concurrency lives here, cadence stays in
    `heartbeat.py`. Each target runs in its **own git worktree** (`git worktree
    add` on a per-target branch from `HEAD`) under a worktrees root, so
    per-iteration `GitCheckpoint` snapshot/`reset --hard` rollbacks are isolated
    (a safety rollback in one worktree never touches another). Concurrency is
    **bounded** by `max_parallel` via a `ThreadPoolExecutor` (excess targets
    queue); a crashed run is captured as a failed `ParallelResult` and does not
    abort its siblings; every worktree is removed (`worktree remove --force` +
    `prune`) on completion, success or crash. Duplicate keys and a zero cap are
    rejected.
  - **Concurrency-safe `MemoryStore`** (`memory/store.py`): the store was
    single-writer; parallel writers on separate connections would hit `database
    is locked`. Decision implemented concretely — **serialize every write
    through a single shared connection guarded by a re-entrant lock, in WAL
    mode**: `check_same_thread=False` (so one connection is shared across worker
    threads), an `RLock` wrapping every statement+commit (and reads, so a row is
    never read mid-write), plus `busy_timeout`. N parallel loops record
    independently without corruption.
  - **Scheduler fan-out hook** (`scheduler/heartbeat.py`): new `tick_parallel`
    fires every due target through `run_parallel`, rebasing each `ScheduledFire`
    onto its per-target worktree; successful fires record the run id as the
    resume anchor, failures are stamped (no anchor) and isolated — same cadence
    semantics as the sequential `tick`. The sequential `tick` is unchanged.
  - **Worktree-aware `GitCheckpoint`** (`loop/checkpoint.py`): documented that
    because every `git` call is `git -C`-scoped, snapshot/restore operate only
    on the given worktree's branch and working tree — making it safe for
    parallel runs (no code change needed; the path scoping already provided it).
  - Tests: `tests/test_parallel_worktrees.py` (new) — real temp git repo + temp
    DB, hermetic: independent checkpoint/rollback across two worktrees, A's
    rollback leaving B untouched, the concurrency cap honored, a crashed run
    recorded + cleaned up while siblings continue, concurrent SQLite writes not
    corrupting, and the `heartbeat.tick_parallel` integration.
- **Catalog-to-proof pipeline, Phase A** (plan
  `docs/plans/2026-06-15-003-feat-catalog-proof-pipeline-plan.md`): turns real
  clianything.cc / printingpress.dev CLIs into verified before/after loop proofs
  by adopting them as refine-only baselines — proving the loop's own value, not
  the generators it wraps.
  - **Catalog adopter** (`src/loopeng/adopt.py`, U1): installs an already-generated
    catalog CLI into a workspace as a baseline. Security-first (KTD7): installs
    into an isolated `--target`/venv dir, spawns the install with a
    credential-pruned environment so third-party install-time code can't read
    ambient secrets, pins by a **full 40-char commit SHA** (tags/branches
    rejected), and only adopts from an allowlisted catalog host. `run_tool` gained
    an `env=` parameter to support the pruned environment.
  - **Refine-only loop entrypoint** (`run_refine_loop` in
    `src/loopeng/autonomous/runner.py`, U2): drives the loop over an
    already-present tool with no generate step — the controller's initial judge
    is the recorded "before" baseline (controller unchanged, KTD1). Adds
    `preflight.missing_for_refine` (gates on judge + refinement engine only, no
    factory) and stamps wall-clock end via the new `runs.finished` column.
  - **Proof pack** (`src/loopeng/proof.py`, U3): `ProofPack.from_run` assembles
    before/after grades, per-dimension score diff, iterations, elapsed, token
    cost (best-effort; omitted, never faked), and compounded regression tests.
    `StoreBackedCompounder` records each accepted-fix learning to the store so
    the proof's regression-test field is real. Result schema extended additively
    with an optional `proof` block (existing illustrative fixtures still
    validate). Secret-scan pattern set broadened (bearer/JWT, GCP, HuggingFace,
    Stripe). `claude -p --output-format json` token usage is now parsed.
  - **`loop-anything demo proof <id>`** (`src/loopeng/cli.py`, U4): orchestrates
    adopt → refine loop → proof pack → record. Flips a card to `live_verified`
    only through the shared `demo record` write path (KTD2); a safety-blocked run
    is recorded as `blocked_safety`, never as a passing proof (R6). `--dry-run`
    prints the plan without writing. The showcase now headlines the before/after
    proof line on verified cards.
  - **Proof targets** (U5): `arxiv` (first-light), `hackernews`, `wikipedia`
    manifests (public-API, no-credential, service lane) + self-contained
    per-target CLI-Judge adapters under `demos/adapters/`. CLI-Judge ships its
    own generic D1–D5 fixtures, so the adapter is the only target-specific piece.
    Cards ship in **draft** (no fabricated trajectory) until a real proof runs.
  - **Gated proof e2e** (`tests/e2e/test_proof_loop.py`, U6): drives the
    refine-only proof against a real adopted tool; skips (never fails) when the
    `claude -p` quota, the grader, or the target are absent.
  - **Docs** (U8): `CONTRIBUTING-demos.md` proof-target section (adopt flags,
    fixture provenance, human-review + full-SHA rules); `docs/solutions/`
    decision records (refine-only baseline, provenance honesty, adopter
    isolation, P0 gate status); `docs/e2e-runbook.md` proof run steps.
  - **Provider-agnostic LLM refiner** (`src/loopeng/adapters/llm_refiner.py`):
    a claude-free, quota-free `Refiner` that drives any OpenAI-compatible chat
    endpoint with a free-tier **fallback chain** (NVIDIA NIM → Groq → Gemini →
    local Ollama, per the `free-llm` design) using stdlib `urllib` (no new
    dependency). Edits are applied as jailed full-file rewrites
    (`within_workspace`); model output is never executed. `demo proof` gains
    `--refiner claude|llm`; preflight's refine gate drops the compound-engineering
    requirement for `llm`; the gated proof e2e accepts `LOOPENG_PROOF_REFINER=llm`
    with a free provider key instead of the `claude -p` quota. This removes the
    quota as a hard blocker on running a real before/after proof.
- Project scaffold: `pyproject.toml`, `loop-anything` CLI entrypoint, package
  layout under `src/loopeng/` (U1).
- `AGENTS.md` agent guide and GitHub Actions CI (pytest on Python 3.11–3.13 for
  every push/PR to `main`).
- Dependency preflight (U1) detecting all four external tools, with per-tool
  detection by mechanism (PATH binary vs. Claude Code skill) so skill-distributed
  tools are not false-negatived; `LOOPENG_ASSUME_*` env override for
  unconfirmable skills.
- `/loop-anything` agent skill (`skills/loop-anything/SKILL.md`) (U1, R10).
- SQLite memory layer (U2): runs/iterations/learnings schema with trend,
  plateau, and recurring-failure queries.
- Target router (U3): classifies a target into the service or codebase lane,
  with `--lane` override.
- Loop controller core (U6): state machine (route/generate/judge/refactor with
  CONVERGED, BLOCKED_SAFETY, STOPPED terminals), multi-signal convergence policy
  (target grade, plateau, iteration/token budget), safety hard-gate, and
  regression rollback — driven through injectable `Judge`/`Refiner` protocols and
  validated against recorded verdicts (de-risks loop dynamics before any live run).
- Factory adapter shells (U4): `PrintingPressFactory` and `CLIAnythingFactory`
  with `shell=False` subprocess execution, shell-metacharacter rejection,
  timeout/exit-code normalization, and a single `_build_command` seam for the
  documented surface.
- Judge adapter shell (U5): `CLIJudge` + `parse_report` with strict
  safety-gate derivation (`safety_ok` False on gate failure or C-cap; fails
  closed on a missing/malformed report). The exact safety field is centralized
  in `derive_safety_ok` for pinning against a real `report.json`.
- `GitCheckpoint` (in `loop/`, reused by U6 and U8 per the U6→U8 dependency fix)
  and the autonomous runner shell (U8): preflight gate, credential gate
  (env-only, never logged), workspace boundary, git checkpoints — wiring
  preflight → route → factory → controller, injectable for testing.

### Added — loop-anything-hub + live-run prep
- **loop-anything-hub:** a GitHub Pages workflow (`pages.yml`) that builds the
  showcase catalog and publishes it on every push to `main` —
  https://wjlgatech.github.io/loop-engineering-anything/
- `loop-anything showcase --base-url <url>` so hosted report/recipe/contributing
  links resolve to GitHub blob URLs (relative when local).
- `loop-anything demo run` now **really attempts** the generator via `claude -p`
  (`/printing-press` or `/cli-anything`) instead of a hardcoded stub: it surfaces
  the real upstream error today (quota) and will produce a tool once quota/Go are
  available, then point to the grade + record step.

### Changed — demo honesty pass
- Relabeled two demos so the domain matches the real target: `smart-grid` →
  *Weather & forecasting* (Open-Meteo is weather, not grid control), `supply-chain`
  → *Aviation tracking* (OpenSky is flights, not freight). The grand grid/logistics
  loops remain as recipes.
- Made the two codebase-lane targets real: vendored `services/example-microservice`
  and `services/example-curriculum` (were placeholder paths).
- Removed a fabricated `blocked_safety` status from `supply-chain` (it was decorative,
  to show the badge); badge coverage now lives in a synthetic generator test.
- Added `demos/README.md` stating plainly that all demos are `illustrative` and **why
  none are `live_verified`**: both generators are Claude Code skills driven by
  `claude -p`, which is quota-blocked until 2026-07-01 — so a verified card can't be
  produced today and won't be faked.

### Added — community demos + showcase
- Demo manifest format + registry (`demos/`, `src/loopeng/demos/`): YAML manifests
  validated by JSON Schema with semantic guards (https-only + non-private host for
  service targets, repo-relative no-`..` for codebase, credential-string rejection);
  result fixtures carry explicit `source` provenance (`illustrative`/`live_verified`).
- `loop-anything demo` CLI (list/show/validate/record/run) — `validate` is the CI
  gate; `record` snapshots a real run into a verified fixture + persisted report;
  `run` is an honest gated stub until per-target adapters land.
- `loop-anything showcase` — self-contained HTML catalog generator: context-aware
  encoding + URL allow-list, card-state table headlining grade trajectory +
  provenance badge, recipes lane, contributor leaderboard, empty/hero/a11y states.
- 10 starter demos from the *Infinite Improvement Loop* domains (concrete targets,
  illustrative fixtures) + 5 `kind: recipe` manifests and `docs/recipes/` docs for
  domains beyond the engine.
- Community contribution path: `CONTRIBUTING-demos.md`, a demo PR template, and a
  `demos.yml` CI workflow running `demo validate` on `demos/**` changes.
- Declared `pyyaml` + `jsonschema` dependencies (manifest format).

### Added (continued)
- History Compression Engine (U7): periodic System-2 consolidation pass with a
  grade-neutral-or-better-and-safe guard (rolls back otherwise); wired into the
  controller on an accepted-fix cadence via an injectable `compressor`.
- Headless refinement bindings (P0 #1): `ClaudeCodeRefiner` / `ClaudeCodeCompounder`
  drive `/ce-work` and `/ce-compound` non-interactively via `claude -p` — a
  concrete answer to "can the loop run unattended?" (quality on real targets stays
  empirical).
- Grade-stability probe (P0 #2): `probe_grade_variance` + `loop-anything
  judge-variance` measure judge jitter; `Budget.min_score_gain` + a noise-aware
  `is_improvement` make the loop ignore sub-noise gains.
- Gated end-to-end reference-loop test (`tests/e2e/`) and `docs/e2e-runbook.md` —
  skipped unless the live tools + credentials are configured.

### Verified against the live CLI-Judge
- Installed CLI-Judge (`pip install -e harness`) and ran it for real. **Pinned the
  judge adapter to the actual `report.json` schema:** the safety signal is
  `safety_blocker` (boolean), dimensions are `D1..D5` with `points`/`max_points`,
  and failing fixtures derive from `tasks[]` that lost points. `CLIJudge` now
  passes `--out` and reads `<tool>/.cli-judge/report.json`.
- **P0 #2 resolved empirically:** the variance probe over the live judge returned
  identical grades across runs (spread 0.0) — CLI-Judge is deterministic, so
  single-run grades are a safe control signal (`min_score_gain` can stay 0).
- Ran the real loop: `LoopController` driven by the live `cli-judge` reached a
  correct terminal state (`STOPPED`/plateau) with a real grade trajectory.
- CLI-Anything generation is a Claude Code *skill* (`/cli-anything <path>`), not a
  build binary; `cli-anything-hub` (`cli-hub`) installs the package manager only.
  CLI-Printing-Press requires a Go toolchain (absent here).

### Changed
- README redesigned for impact: centered hero, badge row (live CI/tests/license),
  mermaid loop + architecture diagrams, pain→fix table, capability columns,
  roadmap checklist, and star-history — modeled on the CLI-Anything layout while
  staying honest about the current 6/8-unit status.

### Investigated / Rejected
- **`command -v` for all four tools** — rejected: CLI-Anything and
  compound-engineering are distributed as Claude Code skills, not PATH binaries,
  so a uniform binary probe false-negatives a correctly-installed environment
  (doc-review finding F-5). Detection is now per-tool by mechanism.
- **Monorepo vendoring the four tools** — rejected (KTD1): immediate staleness
  and large maintenance surface; adapters get the same capability thinner.

### Deferred (gated on external tools + open feasibility questions)
- Binding the U4/U5/U8 shells to the live tools — `_build_command` surfaces and
  the `report.json` safety field must be pinned against installed versions.
- A live `Refiner`/`Compounder` driving real `/ce-work` and `/ce-compound`.
- History Compression Engine (U7) and the e2e reference loop against a real
  public API.
- **P0 gates to resolve before binding the live loop:** whether `/ce-work` and
  `/ce-compound` can be driven headlessly from a long-running controller, and
  whether CLI-Judge grades are stable enough to be a control signal.
