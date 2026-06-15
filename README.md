# loop-engineering-anything

A **loop orchestrator** that turns any target — a public service/API or a local
codebase — into a self-improving, agent-native CLI by driving four existing
tools around a closed feedback loop.

The novel part is **not** another CLI generator. It is the controller, memory,
and convergence policy that wire the existing factories and referee together so
a target keeps improving on its own:

```
target → [router] → factory (CLI-Anything | CLI-Printing-Press)
       → CLI-Judge → report.json (grade + failing dimensions)
       → if grade < A and safety OK and budget left:
             /ce-work refactor brief → re-judge   ↺
       → else: stop. /ce-compound the learnings. emit research report.
```

## Why

Building agent-native tooling today is a one-shot act: generate a CLI, eyeball
it, stop. Nothing verifies the result against reality, feeds failures back into
improvement, or prevents quality degrading as an agent iterates recursively
(the "flying turd" effect). loop-engineering-anything closes that loop, grounded
in CLI-Judge's reality-based grades rather than code-pattern inspection.

## The four tools it drives

| Tool | Lane / Role |
|---|---|
| [CLI-Printing-Press](https://github.com/mvanhorn/cli-printing-press) | service/API lane — URL/HAR/OpenAPI in, SQLite-backed CLI out |
| [CLI-Anything](https://github.com/HKUDS/CLI-Anything) | codebase lane — local software → agent-native CLI |
| [CLI-Judge](https://github.com/wjlgatech/cli-judge) | referee — grades the tool against reality (`report.json`) |
| [compound-engineering](https://github.com/EveryInc/compound-engineering-plugin) | brain — `/ce-work` refactors, `/ce-compound` records learnings |

These are installable **dependencies**, wrapped behind adapters — not forked.

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
loop-anything preflight
```

## Usage

```bash
loop-anything run <target> --goal "<goal>" [--lane service|codebase]
loop-anything status
loop-anything report <run_id> [--json]
```

## Status

Implemented and tested (57 tests): project scaffold + dependency preflight,
SQLite memory layer, target router, the loop-controller core (state machine,
convergence policy, safety hard-gate, regression rollback) validated against
recorded judge verdicts, plus **adapter shells** for the factories (U4), judge
(U5), git checkpoint, and the autonomous runner (U8) — real subprocess
execution, `report.json` parsing, and end-to-end wiring, tested with mocked
tools.

Still pending: binding those shells to live tool installs, a real
`/ce-work`/`/ce-compound` refiner, the History Compression Engine (U7), and the
e2e reference loop against a real public API. Two feasibility gates precede the
live binding — see `AGENTS.md` and `docs/plans/`.

## Tests

```bash
pip install -e ".[dev]"
pytest
```
