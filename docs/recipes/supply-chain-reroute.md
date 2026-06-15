# Autonomous logistics reroute (recipe)

> **Recipe — not runnable yet.** This is an aspirational loop from the *Infinite
> Improvement Loop*; the engine does not execute it today. See its runnable
> narrow demo in the showcase.

## The loop
A Vendor Negotiator + Warehouse Balancer monitor factory output, route delays, and pricing, iterating rerouting until the most cost-effective plan that prevents depletion.

## What it would need
Live logistics feeds as target, a cost/depletion model as the referee, and an exit criterion of 'least-cost plan with no warehouse depletion'.

## Why it isn't runnable yet
Requires live logistics data + a cost-simulation judge with no CLI-Judge fixtures. The narrow `supply-chain` demo (tracking CLI) IS runnable; the reroute loop is not.
