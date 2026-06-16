# loop-anything-hub design rubric (the "judge" for our own showcase)

We dogfooded the loop on our own showcase: treat **printingpress.dev**'s design as
the reality signal, score the generated hub against this rubric (the judge),
refactor `src/loopeng/showcase/generate.py` (the `/ce-work` step), re-render, and
re-score until the grade stops climbing. This file is the rubric; the
`dogfood-log.md` (marketing/) records the trajectory.

Scored A–F per dimension; the showcase must not regress on self-containment or
the security/escaping invariants regardless of aesthetics.

| Dim | What good looks like (from printingpress.dev) | Before | After |
|---|---|---|---|
| **D1 Hierarchy & type** | Strong, calm typographic hierarchy; refined system/sans stack with OpenType features; mono only for code/identifiers; clear h1→h2→card-title scale | C | A |
| **D2 Palette & contrast** | Clean light canvas, dark charcoal ink, muted-gray secondary, ONE restrained accent; local contrast holds on tinted chips. (10× over the reference: dark-mode-aware.) | C | A |
| **D3 Layout & whitespace** | Generous vertical rhythm (section gaps), comfortable card padding, a real top nav/header, centered readable measure | C | A |
| **D4 Cards** | Flat — borders define, not heavy shadows; large radius; generous padding; subtle hover; outcome (trajectory) is the headline | B | A |
| **D5 Chips & badges** | Pill shape, soft-tint fills, uniform within a row, no one-edge accents; scannable filters | B | A |
| **D6 Self-containment (hard gate)** | One file, inline CSS/JS, zero external assets (no webfont/CDN) — KTD7 | A | A |
| **D7 Security/escaping (hard gate)** | Context-aware escaping unchanged; no untrusted string in a JS literal | A | A |

**Before grade: C** (dark GitHub-clone palette, thin hierarchy, no nav, shadow-less but cramped).
**After grade: A** — adopts printingpress.dev's flat, generous, type-led pattern while keeping the two hard gates and a dark-mode-aware palette as the 10×.

**Compounded learning:** the polish came from *typography + whitespace + flat
borders*, not color — exactly the reference's "specificity/restraint over
ornamentation." A light canvas with one accent and a dark-mode fallback reads as
"polished tool," not "AI demo."
