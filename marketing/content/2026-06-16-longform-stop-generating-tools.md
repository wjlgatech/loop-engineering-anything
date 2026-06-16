---
title: "Stop Generating Tools. Start Engineering Loops."
date: 2026-06-16
channel: long-form article (blog / Substack / dev.to)
source_pattern: marketing/PATTERN.md (v1)
status: draft
word_count: ~1500
---

# Stop Generating Tools. Start Engineering Loops.

## The bug hiding in every AI-built tool

Ask an AI to build you a CLI for some API and it will. You skim the output, it
looks plausible, you ship it. And then it sits there — frozen at whatever quality
it happened to have the moment it was generated.

That freeze is the bug.

There is no force in the loop closing the gap between *"it exists"* and *"it's
actually good."* The model doesn't know if the tool handles pagination, or
mis-classifies an auth error, or silently drops a field on the third page of
results. You don't know either, until it bites you in production. Generation is a
one-shot act. Quality is not.

The industry's answer so far has been "use a better model" or "write a better
prompt." Both help the *single shot*. Neither closes the loop. **The next unit of
leverage isn't the prompt — it's the loop around it.**

That's the thesis behind [`loop-engineering-anything`](https://github.com/wjlgatech/loop-engineering-anything),
an open-source engine we built to make any software improve itself. It runs on
your machine; your code never leaves it.

## What it actually does

Point it at a target — an API/service or a local codebase — and a goal. It builds
an agent-native CLI, then enters a closed feedback loop:

**route → generate → judge → refactor → re-judge → compound**

It keeps refactoring until the grade stops climbing, then hands you a report on
how it got there: the grade trajectory, what it changed, and what it learned.
That's the "I'm going to the beach" workflow — kick it off, walk away, read the
report.

The model provides the intelligence. The loop provides the *execution*. Here's
why each step matters.

## 1. The judge is independent — quality comes from reality, not vibes

The single most important design decision: **the thing that decides quality is not
the thing that writes the code.**

An independent referee (CLI-Judge) grades the generated tool on **five
dimensions, A–F**, against *real captured payloads* — actual responses from the
target, not synthetic happy-path examples the model dreamed up. The controller
that drives the loop never inspects code patterns to judge quality. It reads one
thing: the verdict.

This kills the most insidious failure mode in agentic systems — the model
grading its own homework. A maker that scores itself will always find a way to
declare victory. So we enforce, as a hard precondition before any loop runs, that
the **maker ≠ the checker**: the refiner and the judge must be distinct. A
reward-hacked "looks great to me" can't happen, because the thing being graded has
no vote.

## 2. It can't degrade — multi-signal convergence

Naïve agent loops have a nasty habit: run them long enough and they slowly make
things *worse* — the "flying turd" effect, where each iteration drifts further
from the goal while insisting it's improving.

The convergence policy here is multi-signal by construction. The loop stops at the
first of **four** conditions:

- **Target grade reached** — the goal is met.
- **Plateau** — no gain over N iterations; pushing further is wasted budget.
- **Budget** — an iteration, token, or wall-clock ceiling is hit.
- **Safety block** — terminal, and unbypassable.

And crucially: a refactor that *doesn't* raise the grade is rolled back to the
previous checkpoint. The loop only keeps changes that demonstrably help. It cannot
wander downhill.

## 3. It compounds — every fix becomes a regression test

Most tools forget. Fix a bug today, and nothing stops the same bug returning next
week. This loop does the opposite: **every accepted fix is recorded as a learning
plus a regression test.** A solved problem is locked in. The system gets *harder
to break* the longer it runs — the compounding curve, not the sawtooth.

All of it lands in a local SQLite memory, which unlocks queries a stateless run
could never answer: grade trends over time, which fixtures recur across runs,
where a target keeps plateauing. The memory isn't a logbook — it's an input. A
later run starts knowing what defeated the earlier ones.

## 4. Safety is terminal, and "done" is a claim

Two guarantees that matter when you're letting software rewrite software
unattended:

- **An unsafe tool never ships.** A safety failure caps the grade and puts the
  loop in a terminal blocked state. It doesn't matter how high the tool scored on
  the other four dimensions — unsafe is unsafe, and it's rolled back, not shipped.

- **"Converged" is a claim until a human confirms it.** A converged result is
  marked as a *claim*, not a shipped fact. An anti-cognitive-surrender gate
  requires a human to confirm before anything is treated as done — and that gate
  can't be silently bypassed by a caller or a scheduler. When the gate fires, it
  tells you *why* (the borderline dimension and score) so you make a decision, not
  a rubber-stamp.

## The architecture: wrap, don't fork

`loop-engineering-anything` is not another CLI generator. It's the **controller,
memory, and convergence policy** that wire four existing tools into a closed loop:

- **CLI-Printing-Press / CLI-Anything** — build the agent-native CLI (service lane
  / codebase lane).
- **CLI-Judge** — the reality-grounded referee.
- **compound-engineering** — the brain that refactors and records learnings.

These are driven behind adapters, never forked. The controller depends only on a
handful of protocols (`Judge`, `Refiner`, `Compounder`, `Checkpoint`), which is
why the hardest question — *does the loop converge without degrading?* — can be
proven against recorded verdicts with no live tool required.

## What's proven, and what's still frontier

Honesty matters more than hype with a technical audience, so: the
**convergence/refine loop is the proven part.** Its dynamics are validated against
recorded verdicts and a real installed referee, with **286 tests** green on Python
3.11–3.13. The repo recently shipped six gap-bridges that bring its loop closer to
the full agent-loop anatomy — cross-run memory feeding the next run, a strategy
pivot when a run plateaus instead of just stopping, retry that distinguishes a
flaky tool from a bad change, an enforced cost budget, and a legible human-confirm
gate.

The **fully-agentic generate frontier** — CLI-Anything generation as a live
agentic step, the Go-based service lane, a complete generate-and-refine
end-to-end — still has live work in progress, and the repo says so plainly:
unverified demos ship as *illustrative* until a real run is recorded. We're
marketing the loop, not a finished autopilot for everything.

## We dogfood our own thesis

Here's the part we like best. The engine improves software by running it through a
loop: draft, grade against reality, refactor, compound the learning. So we run
*everything* that way — including this launch. The marketing kit that produced
this article has a grader checklist and a dogfood log; each piece is an iteration
that leaves a learning for the next one. Self-improving software, promoted by a
self-improving process.

## Try it

```bash
git clone https://github.com/wjlgatech/loop-engineering-anything
cd loop-engineering-anything
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
loop-anything preflight        # check the four dependencies
loop-anything run ./my-repo --goal "raise correctness and safety to Grade A"
```

Everyone's optimizing prompts. The teams that pull ahead will optimize loops.

So: which of *your* generated tools is quietly stuck at "good enough"?

⭐ **Repo:** https://github.com/wjlgatech/loop-engineering-anything
🖼️ **Live demo hub:** https://wjlgatech.github.io/loop-engineering-anything/
