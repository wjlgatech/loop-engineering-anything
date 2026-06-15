# Contributing a demo

A demo is one YAML file under `demos/`. Contributing is a PR that adds (or
updates) that file — CI validates it, and `loop-anything showcase` renders it
into the catalog. No infrastructure, no account: just a diff.

## 1. Copy a manifest

Start from an existing one (e.g. `demos/clinical-trials.yaml`) and edit:

```yaml
id: my-demo                 # kebab-case, unique
title: My agent-native CLI
domain: My Domain
target: https://api.example.com/v2   # service: https only, public host
lane: service               # service | codebase
goal: make X agent-native and converge to Grade A
kind: demo                  # demo (runnable) | recipe (aspirational)
contributor: your-handle    # GitHub handle
required_env: [MY_API_TOKEN]  # OPTIONAL — env-var NAMES only, never values
exit_criteria: { target_grade: A, max_iterations: 10 }
result_ref: my-demo.json    # OPTIONAL — a fixture under demos/results/
```

**Target rules (enforced by `demo validate`):**
- service lane → an `https:` URL with a public host (no `http:`, no private/
  link-local IPs — SSRF guard).
- codebase lane → a repo-relative path with no `..` (traversal guard).
- **Never** put a credential value anywhere in the manifest or a fixture — name
  the env var in `required_env`. The validator rejects credential-like strings.

## 2. Add a result (optional but encouraged)

A result fixture makes your card show a grade trajectory instead of "draft".
Put it at `demos/results/<id>.json`:

```json
{
  "demo_id": "my-demo",
  "source": "illustrative",
  "grade_trajectory": ["C", "B", "A"],
  "final_grade": "A",
  "convergence_status": "converged",
  "report_ref": "my-demo.report.md"
}
```

- `source: illustrative` — a representative, hand-authored trajectory. The card
  is badged **"illustrative — not a verified run"** so it never overstates.
- `source: live_verified` — **only** produced by snapshotting a real run:
  `loop-anything demo record my-demo --from <run_id>`. Don't hand-write this.

## 2b. Contributing a *proof* target (refine-only pipeline)

A **proof target** goes further than a demo card: it adopts a real, already-built
CLI from [clianything.cc](https://clianything.cc/) /
[printingpress.dev](https://printingpress.dev/) as a **baseline**, runs the loop
(judge → `/ce-work` → re-judge → `/ce-compound`), and records a `live_verified`
before/after **proof pack**. It proves the refine loop — not the generate
frontier.

Two extra artifacts beyond the manifest:

1. **A CLI-Judge adapter** at `demos/adapters/<id>.py`. Copy `demos/adapters/arxiv.py`
   — it is self-contained (CLI-Judge loads it standalone and requires a
   module-level `ADAPTER`), resolves the tool binary from `LOOPENG_PROOF_BINARY`,
   routes replay traffic via base-url env names, and captures a non-zero exit
   instead of raising. CLI-Judge ships its own generic D1–D5 fixtures, so you do
   **not** author per-target payloads — the adapter is the only target-specific
   code.
2. **A pinned, reviewed baseline.** Run the proof with a **full 40-char commit
   SHA** (tags/branches are rejected — KTD7) and review the upstream source at
   that SHA before adopting; the host allowlist gates *where* code comes from,
   not *what* it does.

```bash
# dry-run first (writes nothing):
loop-anything demo proof arxiv --catalog printing-press --name arxiv \
    --sha <full-40-char-commit-sha> --install-kind pp_binary --dry-run
```

**Honesty rules (non-negotiable):**
- A card flips to `live_verified` ONLY via `demo proof` / `demo record` against a
  real run. Never hand-edit a fixture to `live_verified`.
- A `blocked_safety` run is recorded as `blocked_safety`, never a passing proof.
- A no-gain run is recorded honestly as-is — a green before/after is not the goal;
  an honest one is.
- Until a real run lands, leave the card in **draft** (no fixture) — do not ship a
  fabricated `illustrative` trajectory for a proof target.

Live runs need the `claude -p` refine quota and the target's toolchain/daemon;
absent them the gated e2e (`tests/e2e/test_proof_loop.py`) skips, never fails.

## 3. Validate + preview

```bash
pip install -e ".[dev]"
loop-anything demo validate          # the same gate CI runs
loop-anything showcase --out showcase.html   # preview your card
```

## 4. Open a PR

Use the demo PR template. CI runs `loop-anything demo validate` on any PR that
touches `demos/`; a malformed manifest, an unsafe target, or an embedded secret
fails the check. Once merged, your card (and contributor credit) appears in the
catalog.
