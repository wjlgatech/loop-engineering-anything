# Dogfood log — the marketing loop

We treat promotion the way the engine treats software: **draft → grade → revise →
ship → record the learning**, so each launch starts smarter than the last. Every
promotional iteration gets an entry. Be honest; a rejected idea recorded is worth
more than a vague win.

Entry template:
```
## NNN — YYYY-MM-DD — <channel> — <what was launched>
- Hypothesis: <what we believed would work / what we tested vs. last time>
- Changes vs. last iteration: <what we deliberately varied>
- Grade (pre-publish, checklist §4): <pass/fail + the weakest beat>
- Result (after posting): <impressions / reactions / comments / stars / signups — fill in later>
- Learned: <the durable lesson>
- Next test: <the one thing to vary next time>
```

---

## 001 — 2026-06-16 — kit creation (LinkedIn + X + Show HN) — loop-engineering-anything launch

- **Hypothesis:** A repeatable *kit* (one fact base → channel-shaped assets) plus
  a single ownable thesis ("Stop generating tools. Start engineering loops.")
  will outperform a one-off post, and the dogfood angle ("even this launch is a
  loop") is a memorable, on-brand differentiator the source pattern lacks.
- **Changes vs. last iteration:** First iteration — established the pattern
  (`PATTERN.md`), the template, and the grader checklist.
- **Grade (pre-publish, checklist §4):** Pass. Weakest beat: the hook competes
  with the existing repo tagline rather than topping it — kept the tagline as the
  hook because it's already strong and ownable, but flagged for A/B.
- **Result:** _not yet posted — fill in impressions/reactions/comments/stars._
- **Learned (from building it):**
  - The source pattern's power is *specificity over adjectives* — our 10× had to
    earn every number against the repo's real fact base, which forced an honesty
    pass (we cut any "fully autonomous on anything" claim; the generate frontier
    is deferred).
  - The product's own thesis (loops > prompts) doubles as the marketing thesis —
    rare alignment that makes the dogfood angle land instead of feeling cute.
- **Next test:**
  1. A/B the hook — tagline ("Stop generating tools…") vs. pain-first ("Your AI
     writes a CLI once and freezes it. That's the bug.").
  2. Measure whether the dogfood/meta line earns its place or distracts a
     first-time reader (drop it in the short variant and compare).
  3. Confirm the "286 tests" number is current before posting.

---

## 002 — 2026-06-16 — long-form + 2 short A/B posts — applying the kit

- **Hypothesis:** The kit (one fact base + template + grader) can produce a
  full-length in-depth article AND two short posts that A/B the hook, all
  consistent and all defensible — proving the kit scales across formats, not just
  one post shape.
- **Changes vs. 001:** First *application* of the kit. Produced three dated
  instances in `marketing/content/`: a ~1500-word article
  (`2026-06-16-longform-stop-generating-tools.md`) and the two hook variants the
  001 "next test" flagged — pain-first (`short-a`) and thesis-first (`short-b`).
  Re-verified the test count against `main` before citing it (286, still current).
- **Grade (pre-publish, checklist §4):** Pass on all three. Notes:
  - Long-form: numbered mechanism became section headers (altitude shift for
    article length); kept the thesis in title + close; honesty section is explicit
    about the deferred generate frontier.
  - Shorts: both lead with a single ownable claim, one numbered mechanism, one
    engagement question, one CTA. Variant A opens on pain, B on thesis — the only
    deliberate difference, so the A/B is clean.
- **Result:** _not yet posted — fill in per-variant impressions/reactions/comments._
- **Learned (from building it):**
  - The "N dimensions / N stop-signals" device carries the article the same way
    it carries the short post — specificity scales across length.
  - Dating + frontmatter (`date`, `channel`, `hook_variant`) makes instances
    self-describing and lets the dogfood log reference them unambiguously.
- **Next test:**
  1. Post A and B to the same channel a few days apart; compare engagement on the
     two hooks and record the winner here.
  2. For the long-form, test whether opening with the "bug hiding in every
     AI-built tool" frame outperforms a straight "what it does" lede.
  3. Roll the winning hook back into `linkedin-launch.md` as the new default.

---

## 003 — 2026-06-16 — hub promotion: README applications-to-top + 3 application posts

- **Hypothesis:** Surfacing the *breadth of applications* (10 loop domains) at the
  top of the README — plus per-application posts that paint one vivid picture each
  — converts "interesting engine" into "I could build X with this," driving hub
  visits and demo/recipe contributions better than a generic launch post.
- **Changes vs. 002:** New content shape — *application/use-case* posts (not
  product-overview posts). Each leads with an "imagine a loop that…" frame for one
  domain, applies the loop mechanism in that domain's terms, and ends with a
  contribute invite (one PR adds the recipe). Produced three:
  `app-pr-lifecycle`, `app-clinical-trials`, `app-smart-grid` (dev / science /
  infra spread). README: moved the loop-anything-hub showcase to the top as a
  10-row applications grid with an explicit "← your application here" invite.
- **Grade (checklist §4):** Pass. Honesty held: domains are framed as
  roadmap/invitations ("the recipe is mapped, the verified loop is open"), not
  shipped — matches the `illustrative until a live run` badge.
- **Result:** _not yet posted — fill in per-application engagement + any inbound
  contributor interest / demo PRs._
- **Learned (from building it):**
  - Use-case posts need a domain-specific *referee* detail to feel real (real
    trial criteria / real telemetry / CI+review) — the generic "graded against
    reality" line lands harder when bound to the domain's actual signal.
  - The "← your application here" row in the README grid turns a catalog into an
    open invitation in one line.
- **Next test:**
  1. Post the three a few days apart; see which domain pulls the most contributor
     interest, and write the next 3 (legal, quant, supply chain…) toward that pull.
  2. Track whether any post yields a demo/recipe PR — the real conversion metric
     for application posts (vs. reactions for product posts).
