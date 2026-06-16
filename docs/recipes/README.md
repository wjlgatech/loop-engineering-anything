# Loop recipes

**Recipes are not runnable demos.** A *demo* (in `demos/`) is a real target our
engine loops today: generate an agent-native CLI → judge it with CLI-Judge →
refactor → re-judge to a grade. A *recipe* is an **aspirational loop** — a domain
from the *Infinite Improvement Loop* whose full article workflow exceeds what the
engine executes today (live trading, drug-discovery simulation, grid dispatch,
etc.).

We keep recipes honest and separate: each is documented here and carries a
`kind: recipe` manifest so it appears in the showcase's **recipes lane** (clearly
distinct from runnable demos, with no grade trajectory).

Each recipe names:
- **The loop** — the agent personas and the iterate-until exit criteria.
- **What it needs** — the target, the referee/judge, and the exit criteria the
  engine would require.
- **Why not runnable yet** — the specific gap (no referee fixtures for the domain,
  requires live execution we don't sandbox, etc.).

When the gap closes, a recipe graduates to a demo: add a runnable target + a
CLI-Judge adapter, then `loop-anything demo record` a real run.

## Recipes

- [Overnight portfolio optimization](quant-macro-portfolio.md)
- [Molecule design simulation](biotech-drug-sim.md)
- [Predictive grid dispatch](smart-grid-dispatch.md)
- [Autonomous logistics reroute](supply-chain-reroute.md)
- [Trial-protocol refinement](clinical-trial-protocol.md)

> _Graduated to live `live_verified` demos:_
> - **Automate-your-own-job-first** — a real F→A run (`demos/targets/standup/PROOF.md`).
> - **One-person industrial engine** — a real coordinated 2-slice fleet, both slices
>   F→A in dependency order (`demos/fleets/one-person-industrial-engine/PROOF.md`).
