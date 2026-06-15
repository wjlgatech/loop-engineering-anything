# Predictive grid dispatch (recipe)

> **Recipe — not runnable yet.** This is an aspirational loop from the *Infinite
> Improvement Loop*; the engine does not execute it today. See its runnable
> narrow demo in the showcase.

## The loop
A Grid Monitor + Dispatch Meta-Agent ingest consumption and weather, simulate 24h load, and reroute micro-grid discharge each cycle until predicted stability.

## What it would need
A grid simulator as target/referee and an exit criterion of '100% predicted stability, zero maintenance risk'.

## Why it isn't runnable yet
Needs a grid-load simulator as the judge and live dispatch we don't sandbox. The narrow `smart-grid` demo (forecast CLI) IS runnable; the dispatch loop is not.
