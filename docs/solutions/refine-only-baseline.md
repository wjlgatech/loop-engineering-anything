# Refine-only baseline: adopt catalog CLIs instead of generating

**Decision.** The catalog-to-proof pipeline runs the loop **refine-only** on an
already-generated CLI adopted from clianything.cc / printingpress.dev, treating
that published tool as the "before" baseline. It does **not** generate from
scratch.

**Why.** `LoopController.run(run_id, tool_path, goal)` already judges the tool
as-is *before* any refactor (`src/loopeng/loop/controller.py`), and the Factory
protocol is never called by the controller. So refine-only needs no controller
change and no "skip-generate" flag — just a runner fork (`run_refine_loop`) that
omits the generate step. This sidesteps the unproven generate frontier (Go
toolchain for Printing-Press; untested agentic `/cli-anything`) and proves the
loop's actual novel contribution — the convergence loop — rather than the
generators it wraps. "Before/after" becomes catalog-v0 → loop-converged, a
fairer and more feasible comparison than "no tool → tool".

**Scope honesty.** These proofs validate the **refine loop**, not generation.
The README headline ("builds … and refactors") is reconciled with this: verified
cards and the showcase state that the baseline is a published catalog CLI.

**Rejected:** adding a `skip_generate` flag to the `Factory` protocol — the
controller already excludes Factory, so the flag would be dead weight.

See `docs/plans/2026-06-15-003-feat-catalog-proof-pipeline-plan.md` (KTD1).
