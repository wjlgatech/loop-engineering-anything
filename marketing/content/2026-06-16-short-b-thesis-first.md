---
title: "Short post B — thesis-first hook"
date: 2026-06-16
channel: LinkedIn / X (short)
source_pattern: marketing/PATTERN.md (v1)
hook_variant: thesis-first (A/B test vs. variant A)
status: draft
---

Stop generating tools. Start engineering loops.

Everyone's optimizing prompts. But a smarter prompt still ships software that's frozen the moment it's generated — with nothing to close the gap between "it exists" and "it's good."

So we open-sourced **loop-engineering-anything**: point it at any API or codebase and it builds an agent-native CLI, then improves it in a closed loop.

The trick isn't the model. It's the loop:

1. An independent referee grades the tool — 5 dimensions, A–F, against real payloads. Never the model admiring its own code.
2. It refactors the lowest-scoring dimension, and rolls back anything that doesn't raise the grade.
3. It stops at target grade, plateau, budget, or a safety block — so it can't degrade into something worse.
4. Every accepted fix becomes a regression test. A solved problem never comes back.

Runs locally. Unsafe tools never ship. "Done" isn't real until a human confirms it.

The future of AI agents isn't prompt engineering. It's loop engineering.

If a referee graded your last AI-built tool against reality — what grade would it get?

⭐ github.com/wjlgatech/loop-engineering-anything (link in comments)
