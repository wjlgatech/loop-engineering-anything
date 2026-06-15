# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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
