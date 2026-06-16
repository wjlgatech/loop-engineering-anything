# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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
