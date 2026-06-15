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
