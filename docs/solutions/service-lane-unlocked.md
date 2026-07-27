# Service lane unlocked — CLI-Printing-Press live (2026-07-27)

The service/API lane's generate frontier is no longer deferred. Recorded here so
the next run starts from facts, not the old `[MISSING]` preflight.

## Install (pinned, checksum-verified — no `curl | bash`)

- Binary: release **v4.29.0** `cli-printing-press_darwin_arm64.tar.gz` from
  `mvanhorn/cli-printing-press`, sha256 `1909cff372f9669ebce4b740458993e87e15894e...`
  verified against `checksums.txt`, installed to `~/.local/bin/cli-printing-press`
  (+ a `printing-press` symlink for the old adapter default).
- Skills: `npx -y skills@latest add mvanhorn/cli-printing-press/skills --skill '*' -g`
  → 9 `/printing-press*` skills under `~/.claude/skills/`.
- Toolchain: Go 1.26.5 (brew) — generated CLIs are Go/Cobra.

`loop-anything preflight` → `[ok] CLI-Printing-Press (service/API lane)`.

## Adapter bound to the real surface

`PrintingPressFactory._build_command` was a speculative shell
(`generate <target> --out`); v4.29.0's real surface is
`cli-printing-press generate --spec <path|url> --output <dir> --json`.
Now pinned + regression-tested (`test_printing_press_command_is_pinned_to_v4_surface`).

## First live generation (evidence)

Target: **Wikimedia REST API** (the `wikipedia` draft demo's domain) — official
OpenAPI 3.0.1 spec, 46 paths.

- Wikimedia 403s the generator's own fetch (User-Agent policy) → download the
  spec with a proper UA and pass `--spec /tmp/wikipedia-openapi.json
  --spec-url 'https://en.wikipedia.org/api/rest_v1/?spec'` (provenance flag
  exists for exactly this).
- The spec's `servers` entry is relative (`/api/rest_v1`) → the generated
  client needs `WIKIPEDIA_BASE_URL=https://en.wikipedia.org` at runtime.
- Generation gates: **all PASS** (go mod tidy, govulncheck, go vet, go build,
  runnable binary, --help/version/doctor). MCP bundle emitted.
- Live call: `wikipedia-pp-cli page get-summary "Bayesian_optimization" --agent`
  → real JSON envelope, `meta.source: live`.
- Referee: `cli-printing-press scorecard --dir .loopeng/wikipedia` →
  **86/100, Grade A** (auth/live-verification dimensions honestly N/A'd out of
  the denominator).

## Still open

- Wire the wikipedia/arxiv/hackernews draft demos through `demo run` now that
  the lane is live (their `_run_generator` path shells `claude -p /printing-press …`).
- The codebase lane (CLI-Anything) and the chain refiner (`/ce-work` plugin)
  remain uninstalled — vlm-probe's codebase-lane proof ran attended instead.
