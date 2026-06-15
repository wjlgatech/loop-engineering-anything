# Molecule design simulation (recipe)

> **Recipe — not runnable yet.** This is an aspirational loop from the *Infinite
> Improvement Loop*; the engine does not execute it today. See its runnable
> narrow demo in the showcase.

## The loop
A Molecule Designer generates structural variants and a Simulation Evaluator runs cellular-interaction + pharmacological sims, recalibrating parameters each batch until binding affinity and toxicity thresholds are met.

## What it would need
A chemistry toolchain as target, simulation scripts as the referee, and an exit criterion of 'binding affinity > 0.85 with zero toxicity flags'.

## Why it isn't runnable yet
Requires a computational-chemistry simulation environment as the judge; CLI-Judge has no fixtures for it. The narrow `biotech-discovery` demo (PubChem lookups) IS runnable; the molecule-design loop is not.
