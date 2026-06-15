# Trial-protocol refinement (recipe)

> **Recipe — not runnable yet.** This is an aspirational loop from the *Infinite
> Improvement Loop*; the engine does not execute it today. See its runnable
> narrow demo in the showcase.

## The loop
A Clinical Data Analyst + Safety Meta-Agent monitor telemetry for statistical drift and recalibrate recruitment criteria each cycle until trial safety is maximized.

## What it would need
Trial telemetry as target, a statistical-drift + safety-threshold scorer as the referee, and an exit criterion of 'updated protocol within safety bounds'.

## Why it isn't runnable yet
Requires patient telemetry and a clinical-safety judge — neither has CLI-Judge fixtures, and the domain carries real-world safety stakes we won't simulate casually. The narrow `clinical-trials` demo (trial search CLI) IS runnable; the protocol loop is not.
