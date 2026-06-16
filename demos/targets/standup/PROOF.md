# automate-your-job — graduated to a live demo (real F → A)

The **automate-your-own-job-first** recipe graduated to a runnable, `live_verified`
demo. A team-lead's repetitive task — turning a captured day of raw activity
(`activity.json`) into a structured standup digest — was handed to the loop:
the real `cli-judge` referee graded the tool against the **captured task payload**,
and the free-tier `FallbackLLMRefiner` (Gemini, **no Anthropic quota**) refactored
the buggy CLI until it passed.

## Result (real run, 2026-06-16)

| | grade | score |
|---|---|---|
| **before** (baseline `cli.py`) | **F** | 0.0 |
| **after** (loop-refined) | **A** | 100.0 |

- **Trajectory:** `F → A` (CONVERGED, 2 iterations). Refiner provider: `gemini`.
- **Recorded** via the legit path: `loop-anything demo record automate-your-job --from <run_id>`
  → `demos/results/automate-your-job.json` (`source: live_verified`). KTD2 honored —
  the card flips to verified ONLY through the shared record path on a real run.

## The loop

- **Target:** `demos/targets/standup/cli.py` — a daily standup-digest CLI (baseline
  is intentionally buggy: crashing `version`, plain-text non-structured digest).
- **Captured payload:** `demos/targets/standup/activity.json` — one real day of
  activity the lead used to hand-digest. The grade is measured against it.
- **Adapter:** `demos/adapters/automate-your-job.py` — shells the target.
- **Suite + task:** `demos/suites/automate-your-job.yaml` +
  `demos/suites/standup_digest.task.json` / `.fixture.json` — the referee asserts
  the digest is valid JSON with `yesterday`/`today`/`blockers`, and that the
  captured blocker (`staging DB creds`) actually surfaces under `blockers`.
- **Evidence:** `evidence/before.report.json` (F) + `evidence/after.cli.py` (the
  agent-native CLI Gemini produced).

## Reproduce

```bash
# referee (editable from a persistent clone — see repo memory) + a free LLM (free-llm skill):
.venv/bin/pip install -e ~/.cache/loopeng/cli-judge/harness
cp demos/suites/automate-your-job.yaml ~/.cache/loopeng/cli-judge/suites/
mkdir -p ~/.cache/loopeng/cli-judge/fixtures/ayj
cp demos/suites/standup_digest.*.json  ~/.cache/loopeng/cli-judge/fixtures/ayj/
export GEMINI_API_KEY=...     # or local Ollama; chain is gemini -> ollama
# then drive LoopController(CLIJudge(adapter, suite="automate-your-job"), FallbackLLMRefiner())
# against a git-init'd workspace copy of demos/targets/standup/, and
# `loop-anything demo record automate-your-job --from <run_id>`.
```
