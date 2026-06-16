# Automate-your-own-job-first loop (recipe)

> **Recipe — not runnable yet.** An aspirational loop adapted from an AI-agency
> brainstorm; the engine does not execute it end-to-end today (your role's API +
> task fixtures are private). It is the most on-identity of the agency ideas: it
> is literally what loop-anything does — make a target agent-native and grade it
> against reality — pointed at your own toil.

## The reframe

The brainstorm's "Automate Your Own Job First" jiu-jitsu: instead of waiting to be
replaced, build the agents that do 60% of your role, so you *own* the automation.
For a loop engine that maps cleanly — the agency transfer *is* the loop run.

## The loop

Point the loop at the repetitive slice of a role (an internal API, a runbook, a
set of scripts). It generates an agent-native CLI for that slice, an independent
referee grades it against **your real captured task payloads** (did it produce the
right output on last week's actual cases?), and it refactors until the grade
converges — every fix locked in as a regression test so the automation only gets
more reliable.

## What it would need

- **Target:** the role's internal API or repo.
- **Referee:** a CLI-Judge suite + fixtures built from real, captured task
  inputs/outputs for that role (the honest signal — graded against what the job
  actually required, not a synthetic rubric).
- **Exit criterion:** the CLI reliably passes the captured task set at Grade A.

## Why it isn't runnable yet

The referee fixtures are inherently private and per-role — there is no shared,
shippable suite. The mechanism is proven (see
`demos/targets/factcli/PROOF.md` for a real F→A run on a self-contained target);
graduating this to a demo means someone captures a real role's task payloads and
contributes a CLI-Judge adapter + suite for it.
