# LinkedIn — launch post

> Generated from `PATTERN.md` (template §3, graded against checklist §4). Two
> variants: the full post and a short cut. Pick one; log the choice and result in
> `dogfood-log.md`.

---

## Variant A — full (primary)

Stop generating tools. Start engineering loops.

Your AI writes a CLI, you eyeball it, you stop. It's frozen the moment it's born.

Nothing closes the gap between "it exists" and "it's actually good."

So we open-sourced **loop-engineering-anything** to close it.

Point it at any API or any codebase. It builds an agent-native CLI, grades it against reality, and refactors until the grade stops climbing — then hands you a report on how it got there.

It runs on your machine. Your code never leaves.

The trick isn't a smarter model. It's the loop around it:

1. Route — service/API or codebase, auto-detected
2. Generate — an agent-native CLI
3. Judge — an independent referee grades it on 5 dimensions, A–F, against real captured payloads (never the model admiring its own code)
4. Refactor — fix the lowest-scoring dimension
5. Compound — every accepted fix becomes a regression test, so a solved problem never comes back

It stops the moment it should — target grade, plateau, budget, or a safety block — so it can't slowly degrade into a worse tool than it started. A safety failure is terminal: an unsafe tool never ships, no matter how high it scores. And "converged" is a claim, not a fact, until a human confirms it.

We don't just preach this. The engine itself is built by driving four existing tools around one closed loop, proven by 286 tests — and even this launch is run as a loop we keep grading and improving.

Everyone's optimizing prompts. The next leverage is the loop.

So: which of your generated tools is quietly stuck at "good enough"?

⭐ github.com/wjlgatech/loop-engineering-anything
Live demo hub ↓ (link in comments)

---

## Variant B — short cut (faster scroll, mobile-first)

Your AI generates a CLI once and freezes it. Nobody closes the gap between "it exists" and "it's good."

We open-sourced **loop-engineering-anything** to close it — locally, on your machine.

Point it at any API or codebase. It builds an agent-native CLI, then loops:

→ an independent referee grades it (5 dimensions, A–F, against real payloads)
→ it refactors the weakest dimension
→ every fix becomes a regression test
→ it stops at target grade, plateau, budget, or a safety block — never degrading

Unsafe tools never ship. "Done" isn't real until a human confirms it.

Everyone optimizes prompts. The next leverage is the loop.

Which of your generated tools is stuck at "good enough"?

⭐ github.com/wjlgatech/loop-engineering-anything (link in comments)

---

## First comment (drop the links here, per LinkedIn reach mechanics)

Repo: https://github.com/wjlgatech/loop-engineering-anything
Live demo hub: https://wjlgatech.github.io/loop-engineering-anything/

It wraps (doesn't fork) four tools into the loop — CLI-Printing-Press, CLI-Anything, CLI-Judge, and the compound-engineering plugin. The novel part is the controller + memory + convergence policy that turns them into a closed feedback loop. PRs welcome.
