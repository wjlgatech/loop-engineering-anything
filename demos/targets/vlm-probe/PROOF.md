# vlm-probe — cross-repo proof: FM-os probe suite driven to agent-native (F → A)

The first loop over a **cross-repo target**: loop-engineering-anything's
maker/checker machinery pointed at another repo's engine — FM-os
[`skills/vlm-failure-probe`](https://github.com/wjlgatech/FM-os/tree/main/skills/vlm-failure-probe)
(a VLM failure-mode probe suite with an honest no-evidence⇒No gate). The
baseline is a **naive human-facing wrap** of that engine — nothing planted; it
fails the contract simply because it was written for a human. The contract adds
a task no earlier demo had: **gate honesty** (`probe gate --model mock --json`
must exit **1** — a gate that passes the failing model is lying).

## Result (real runs, 2026-07-25)

| run | goal brief | maker | grade | outcome |
|---|---|---|---|---|
| baseline | — | — | **F** (0.0) | fails all 4 tasks |
| #2, #3 | contract only | `FallbackLLMRefiner` (free tier), 6 / 10 iters | **B** (72.2) | honest plateau, `stopped` |
| **#5 (recorded)** | contract **+ the engine's API shape** | `FallbackLLMRefiner` (free tier), 3 iters | **A** (100.0) | **`CONVERGED`** |

- **Recorded run:** run #5 → `loop-anything demo record vlm-probe --from 5` →
  `A, converged`. Evidence: `evidence/before.report.json`,
  `evidence/after.report.json`, `evidence/after.cli.py` (independently re-graded
  A by the referee).
- **The compounding lesson (why #3 plateaued and #5 converged):** with a
  contract-only brief, the refiner *invented* a `probe_result.success` attribute
  (`run_probes` actually returns `{mode_id: {"measured", "score", "threshold",
  "probes"}}` dicts) and crashed `probe run --json` on the same defect across two
  runs (16 total iterations). Adding two sentences of **engine API to the goal
  brief** took the same free-tier maker from a 10-iteration B-plateau to a
  3-iteration A. *The brief is part of the loop: spec the target's API in the
  goal, or the maker will invent it.*
- **Attended detour (kept as evidence):** before the brief was fixed, the
  plateau's defect was closed by hand on a labeled copy
  (`evidence/attended.cli.py` + `evidence/attended.report.json`, A 100.0) —
  useful as the diagnosis that revealed *what* the goal brief was missing. It
  was never recorded as a loop result.
- **Referee:** real `cli-judge` over the `vlm-probe` suite (4 upstream-free
  tasks: the generic D2 banner task + 3 new `d2.vlmprobe.*` tasks, including
  the honest-gate assertion `exit_code == 1` on the failing model).

## What's in the loop

- **Target:** `demos/targets/vlm-probe/cli.py` — the committed naive baseline.
  It resolves the FM-os engine via `VLM_PROBE_SKILL_DIR` (wrap, don't fork).
- **Adapter:** `demos/adapters/vlm-probe.py` — shells the workspace copy one-shot,
  no TTY, resolved via `LOOPENG_PROOF_TARGET`.
- **Suite:** `demos/suites/vlm-probe.yaml` (shippable copy; cli-judge loads it from
  its own checkout's `suites/`), tasks under the checkout's `fixtures/vlmprobe/`.
- **Driver:** `scripts/drive_vlm_probe_proof.py` — mirrors the software-arch driver;
  `VLM_PROBE_MAX_ITERS` and `VLM_PROBE_REFINER` (`llm|claude|chain`) parameterize it.

## Reproduce

```bash
# referee + suite (cli-judge checkout at ~/.cache/loopeng/cli-judge, harness in .venv)
cp demos/suites/vlm-probe.yaml ~/.cache/loopeng/cli-judge/suites/
# grade the committed baseline (expect F):
LOOPENG_PROOF_TARGET=$PWD/demos/targets/vlm-probe \
VLM_PROBE_SKILL_DIR=~/Documents/Projects/FM-os/skills/vlm-failure-probe/reference \
  cli-judge run --adapter demos/adapters/vlm-probe.py --suite vlm-probe --out /tmp/before
# drive the loop (free-tier refiner; GEMINI_API_KEY or local Ollama):
VLM_PROBE_MAX_ITERS=10 LOOPENG_ASSUME_COMPOUND_ENGINEERING=1 \
  PYTHONPATH=src .venv/bin/python scripts/drive_vlm_probe_proof.py
```

## Honest scope

- The `chain`/`claude` refiner tiers shell `/ce-work` via `claude -p`; the
  compound-engineering plugin is **not installed** on this machine, so the chain
  run (run #4, F → F, every refactor rolled back) measures the *environment*,
  not the tier — rerun it where the plugin exists before drawing conclusions.
- The generate step (this baseline) was authored attended following the
  CLI-Anything skill flow (the generators are Claude Code skills; `demo run`
  drives them headlessly via `claude -p` when quota/plugins allow). The
  Printing-Press (service) lane remains unexercised.
