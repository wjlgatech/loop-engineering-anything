# factcli — first real end-to-end live proof (F → A)

This is the project's **first genuine end-to-end loop run**: a real referee
(CLI-Judge) graded a tool, a **free-tier LLM refiner** (Gemini → Ollama chain,
**zero Anthropic quota**) improved it across iterations, and it **converged from
F to A** — no fakes, no recorded verdicts, no hand-editing.

It validates the deferred roadmap frontier (*refine loop, live*) on a
self-contained target that needs no external catalog tool or Go toolchain.

## Result (real run, 2026-06-16)

| | grade | score | failing tasks |
|---|---|---|---|
| **before** (baseline `cli.py`) | **F** | 0.0 | all 3 (`d2.repl.banner_signature`, `d2.noninteractive.mode`, `d2.json.empty_result`) |
| **after** (loop-refined) | **A** | 100.0 | none |

- **Grade trajectory:** `F → F → F → A` (CONVERGED in 4 iterations).
- **Refiner:** `FallbackLLMRefiner`, provider `gemini` (free tier). Two refactors
  were rolled back for no gain; the third accepted refactor passed all three
  contract tasks — the convergence policy + regression rollback working live.
- **Referee:** real `cli-judge` over the `proof` suite (three upstream-free D2
  tasks). Evidence: `evidence/before.report.json`, `evidence/after.report.json`,
  and the converged tool the LLM produced at `evidence/after.cli.py`.

## What's in the loop

- **Target:** `demos/targets/factcli/cli.py` — a tiny CLI with three deliberate,
  fixable bugs (crashing `version`, prompting non-JSON `project new`, `fs ls`
  missing the `items` key). The committed copy stays the baseline; a run mutates
  a workspace copy.
- **Adapter:** `demos/adapters/factcli.py` — shells the target one-shot
  (`from cli_judge.adapter import …`), resolving the workspace via
  `LOOPENG_PROOF_TARGET`.
- **Suite:** `demos/suites/proof.yaml` — the three D2 tasks (reused from CLI-Judge,
  no replay server needed).

## Reproduce

```bash
# 1. Install the referee (editable, from a persistent clone — see the repo memory):
git clone --depth 1 https://github.com/wjlgatech/cli-judge ~/.cache/loopeng/cli-judge
.venv/bin/pip install -e ~/.cache/loopeng/cli-judge/harness
cp demos/suites/proof.yaml ~/.cache/loopeng/cli-judge/suites/   # cli-judge loads suites from its own checkout

# 2. A free LLM for the refiner (no Anthropic) — see the `free-llm` skill:
export GEMINI_API_KEY=...        # or run a local Ollama; the chain is gemini -> ollama

# 3. Grade the baseline (expect F), then drive the loop (expect convergence to A).
#    The driver builds LoopController + CLIJudge(suite="proof") + FallbackLLMRefiner
#    against a git-init'd workspace copy of demos/targets/factcli/.
```

## Honest scope

- This proves the **refine loop** live; the *generate* frontier (CLI-Anything /
  Printing-Press) is still deferred.
- The `proof` suite currently lives in the CLI-Judge checkout's `suites/` dir
  because cli-judge resolves suites from its own repo root; `demos/suites/proof.yaml`
  is the shippable copy. Productionizing (have cli-judge load an external suite, or
  contribute the suite upstream) + wiring this as a recorded `live_verified` hub
  card via the `demo record` path is the immediate next step.
