# Demos

Community demo manifests for the [showcase catalog](../CONTRIBUTING-demos.md). One
YAML file per demo; `loop-anything demo validate` is the CI gate, `loop-anything
showcase` renders the gallery.

## Honest status: every demo here is `illustrative`

None of these have been run live yet. Their grade trajectories are **representative,
hand-authored** values — the cards are badged "illustrative — not a verified run"
so this is never hidden.

**Why none are `live_verified` today:** producing a verified result needs the engine
to *generate* the agent-native CLI, and both generators are **Claude Code skills**
driven by `claude -p`:
- service lane → CLI-Printing-Press (`/printing-press`, also needs Go ≥1.26)
- codebase lane → CLI-Anything (`/cli-anything`)

Headless `claude -p` is **quota-blocked until 2026-07-01** on this account, so the
generate step can't run. CLI-Judge (the referee) *is* installed and works — the
real loop has been exercised against it (see `docs/e2e-runbook.md`), but against
the harness self-test adapter, not these domain targets (which also need a per-target
CLI-Judge adapter, deferred).

A card flips to `live_verified` only via `loop-anything demo record <id> --from
<run_id>` against a real run — never by hand-editing a fixture.

## Honest labels

Two demos use labels that match their **real target**, not the article's grand domain:
- `smart-grid` → *Weather & forecasting* (Open-Meteo is a weather API; it's a
  forecasting input to the grid domain, not grid control). The full grid-dispatch
  loop is a [recipe](../docs/recipes/smart-grid-dispatch.md).
- `supply-chain` → *Aviation tracking* (OpenSky is flight data, not freight). The
  full logistics-reroute loop is a [recipe](../docs/recipes/supply-chain-reroute.md).

The two codebase demos (`software-arch`, `edu-curriculum`) point at **real vendored
example repos** under `services/`, not placeholder paths.
