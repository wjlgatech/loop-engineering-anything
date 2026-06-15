# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project scaffold: `pyproject.toml`, `loop-anything` CLI entrypoint, package
  layout under `src/loopeng/` (U1).
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

### Investigated / Rejected
- **`command -v` for all four tools** — rejected: CLI-Anything and
  compound-engineering are distributed as Claude Code skills, not PATH binaries,
  so a uniform binary probe false-negatives a correctly-installed environment
  (doc-review finding F-5). Detection is now per-tool by mechanism.
- **Monorepo vendoring the four tools** — rejected (KTD1): immediate staleness
  and large maintenance surface; adapters get the same capability thinner.

### Deferred (gated on external tools + open feasibility questions)
- Factory adapters binding to the real CLI-Printing-Press / CLI-Anything (U4)
  and the CLI-Judge adapter (U5) — need the tools installed.
- History Compression Engine (U7) and the autonomous runner + e2e reference loop
  (U8).
- **P0 gates to resolve before binding the live loop:** whether `/ce-work` and
  `/ce-compound` can be driven headlessly from a long-running controller, and
  whether CLI-Judge grades are stable enough to be a control signal.
