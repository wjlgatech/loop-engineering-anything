# software-arch — graduated to a live demo (real F → A)

The **software-arch** recipe ("make a local microservice agent-native") graduated
from an `illustrative` recipe to a runnable, `live_verified` demo. A deliberately
buggy ops CLI over a local in-process microservice (`service.py`) was handed to the
loop: the real `cli-judge` referee graded it against a four-task D2 contract, and
the free-tier `FallbackLLMRefiner` (Gemini, **no Anthropic quota**) refactored the
CLI until it passed.

## Result (real run, 2026-07-19)

| | grade | score | failing tasks |
|---|---|---|---|
| **before** (baseline `cli.py`) | **F** | 0.0/18 | all 4 (`d2.svc.version`, `d2.svc.health`, `d2.svc.items_empty`, `d2.svc.additem`) |
| **after** (loop-refined) | **A** | 100.0/100 | none |

- **Trajectory:** `F → A` (CONVERGED, 2 iterations). Refiner provider: `gemini`.
- **Recorded** via the legit path: `loop-anything demo record software-arch --from <run_id>`
  → `demos/results/software-arch.json` (`source: live_verified`). KTD2 honored —
  the card flips to verified ONLY through the shared record path on a real run.
- **Independently re-graded:** the converged `evidence/after.cli.py` scores A
  (100/100, all four tasks) on a clean re-run of the referee.

## The loop

- **Target:** `demos/targets/software-arch/cli.py` — an ops CLI for the local
  microservice. The baseline is intentionally buggy: `version --json` raises a
  `TypeError`, `health` prints plain text, `items list` emits `no items` (non-JSON,
  no `items` key) on the empty case, and `items add` prompts interactively (hangs
  under no-TTY agent use).
- **Dependency:** `demos/targets/software-arch/service.py` — the in-process
  inventory logic (lifted from `services/example-microservice`) the CLI wraps. The
  refiner edits `cli.py`; `service.py` is the stable codebase it makes agent-native.
- **Adapter:** `demos/adapters/software-arch.py` — shells the target one-shot,
  resolving the workspace via `LOOPENG_PROOF_TARGET`.
- **Suite + tasks:** `demos/suites/software-arch.yaml` + `demos/suites/sa/*.json` —
  the referee asserts each command exits 0, never prompts, and emits valid JSON
  with the expected keys.
- **Evidence:** `evidence/before.report.json` (F) + `evidence/after.report.json`
  (A) + `evidence/after.cli.py` (the agent-native CLI Gemini produced).

## What the loop actually fixed

The accepted refactor made every command non-interactive and JSON-clean: `version`
emits `{"version": ...}` instead of crashing; `health` returns `service.health()`
as JSON with `status: ok`; `items list` always returns `{"items": [...]}` (empty
list included); `items add` drops the `input()` prompt and runs one-shot. Real
fixes to the named failures — not tests gamed.

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"

# referee (from a persistent clone) + the software-arch suite/tasks:
git clone --depth 1 https://github.com/wjlgatech/cli-judge ~/.cache/loopeng/cli-judge
.venv/bin/pip install -e ~/.cache/loopeng/cli-judge/harness
cp demos/suites/software-arch.yaml ~/.cache/loopeng/cli-judge/suites/
mkdir -p ~/.cache/loopeng/cli-judge/fixtures/sa
cp demos/suites/sa/*.json ~/.cache/loopeng/cli-judge/fixtures/sa/

export GEMINI_API_KEY=...          # or local Ollama; chain is gemini -> ollama
PATH="$PWD/.venv/bin:$PATH" LOOPENG_REFINER_CHAIN=gemini \
  .venv/bin/python scripts/drive_software_arch_proof.py
# then: loop-anything demo record software-arch --from <run_id>
```
