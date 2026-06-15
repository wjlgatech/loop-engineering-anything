---
name: loop-anything
description: >
  Turn any target (a service/API URL, HAR, or OpenAPI spec; or a local
  codebase/repo) into a self-improving, agent-native CLI. Routes the target to
  the right factory (CLI-Printing-Press or CLI-Anything), generates the tool,
  grades it with CLI-Judge, and drives a refactor -> re-judge loop until Grade A,
  a safety block, or budget exhaustion -- then compounds the learnings and emits
  a research report. Use for "make X agent-native and keep improving it", or the
  overnight "going to the beach" autonomous run.
---

# loop-anything

`loop-anything` is a **loop orchestrator**. It does not generate CLIs itself; it
drives four existing tools around a closed feedback loop:

| Stage | Tool | Role |
|---|---|---|
| route + generate | CLI-Printing-Press / CLI-Anything | build the agent-native CLI |
| judge | CLI-Judge | grade it against reality (`report.json`) |
| refactor | `/ce-work` | fix the lowest-scoring dimensions |
| compound | `/ce-compound` | record the learning + a regression test |

## Preconditions

Run preflight first — it detects all four dependencies and fails fast if one
required for your lane is missing:

```
loop-anything preflight
loop-anything preflight --lane service     # exit 1 if the service lane is blocked
```

The compound-engineering plugin is detected as a Claude Code skill, not a PATH
binary. If auto-detection cannot confirm it, set
`LOOPENG_ASSUME_COMPOUND_ENGINEERING=1`.

## Usage

```
loop-anything run <target> --goal "<high-level goal>" [--lane service|codebase]
loop-anything status
loop-anything report <run_id> [--json]
```

`<target>` may be a URL, a `.har` file, an OpenAPI spec, or a local directory /
git repo. The lane is auto-classified; `--lane` forces it.

## Safety

CLI-Judge's safety gate caps a tool's grade at C; the loop treats a safety
failure as a terminal `BLOCKED_SAFETY` state and never ships an unsafe tool
(R3). Autonomous runs apply code changes only inside a workspace boundary and
checkpoint every iteration so a regression rolls back cleanly.

## Status

Foundations (scaffold, memory, router, loop-controller core) are implemented and
tested against recorded verdicts. The factory and judge adapters bind to the
real external tools and are built in a later unit; until then `run` routes and
gates on preflight but does not drive the live factories.
