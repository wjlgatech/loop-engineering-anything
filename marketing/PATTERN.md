# The Dev-Tool Launch Pattern (a reusable, dogfoddable playbook)

This is the distilled, reusable pattern for introducing a developer tool/repo on
social (LinkedIn / X / Show HN). It was reverse-engineered from a high-performing
example, evaluated, aligned to this repo, and then **10×'d**. Treat it the way we
treat everything here: as a loop you grade and improve each time (see
`dogfood-log.md`).

> **The meta-point:** this repo's thesis is *loop engineering* — draft → grade
> against reality → refactor → compound the learning. Our marketing is run the
> same way. Each launch is a loop iteration; each iteration leaves a learning so
> the next one starts smarter. **Don't write a post — run a marketing loop.**

---

## 1. The source pattern (reverse-engineered)

The reference post (Microsoft "AI Engineer Coach") works because it executes a
tight 8-beat structure. Each beat has a job:

| # | Beat | Job | Example move |
|---|------|-----|-------------|
| 1 | **Authority/novelty hook** (1 line) | Stop the scroll; promise a concrete payoff | "Microsoft just built a coach that catches your AI coding habits and fixes them." |
| 2 | **Pain, in 2nd person, fragmented** | Make the reader feel the gap | "Most developers… have no idea if they're improving. Which prompts they repeat. Which habits slow them down." |
| 3 | **The reveal** | Name it + lower the risk | "Microsoft just **open-sourced** AI Engineer Coach to fix that." |
| 4 | **1–2 sharp differentiators** as standalone lines | Earn trust fast | "Everything runs on your machine. No data leaves." / "works across any harness" |
| 5 | **Quantified, numbered list** | Make it scannable + credible | "45 anti-pattern rules across five areas: 1… 2… 3…" |
| 6 | **Benefits, not specs** | Translate features to outcomes | "Each flagged issue arrives with a severity rating and a concrete fix." |
| 7 | **Reflective engagement question** | Provoke a comment | "So what habit is quietly capping your output?" |
| 8 | **CTA + social proof** | Convert + de-risk | "Link in comments." / "Read by 300,000+ devs." |

**Why it works (the mechanics):**
- **Specificity beats adjectives.** Numbers ("45 rules", "five areas") and named
  competitors ("Copilot, Claude Code, Cursor") do the persuading. Almost zero
  hype words.
- **Whitespace is a feature.** One idea per line; the eye never tires.
- **Second person.** "you / your" the whole way — it's about the reader.
- **Risk reversal early** ("open-sourced", "no data leaves") removes the two
  reflex objections (cost, privacy) before they form.
- **The "N things across M areas" device** signals "this is rigorous and
  complete" in one phrase.

---

## 2. Our 10× moves (what we add on top)

The source pattern is a single post. We raise the ceiling on five axes:

1. **One source of truth → a kit.** A folder of channel-shaped assets
   (LinkedIn, X thread, Show HN, taglines) generated from one accurate fact
   base, so messaging stays consistent and reusable.
2. **A signature, ownable angle.** The reference is generic ("tool that
   helps"). We lead with a *thesis* the reader can repeat: **"Stop generating
   tools. Start engineering loops."** A claim is more shareable than a feature.
3. **Proof over promise.** Every quantified claim maps to something real in the
   repo (test count, dimensions, stop-signals, the four wrapped tools). No
   number we can't defend. (See "Fact base" below.)
4. **The dogfood angle as the hook's twist.** Because the product *is* a
   self-improving loop, we say so: "even this launch is run as a loop." It's
   memorable, on-brand, and true.
5. **A measured loop, not a one-shot.** Every launch is logged with a
   hypothesis and a result (`dogfood-log.md`), so the pattern itself compounds —
   the same edge the product gives users, applied to our copy.

---

## 3. The fill-in template (any repo)

```
[1 HOOK] <Memorable claim or contrarian truth about the status quo.>

[2 PAIN] <The reader's situation today, 2–3 short fragments.>

[3 REVEAL] We open-sourced <name> to <verb the pain away>.

[4 DIFFERENTIATOR] <The single sharpest thing. A standalone line.>
[4b optional] <Risk reversal: local / free / no lock-in.>

[5 NUMBERED MECHANISM] The trick isn't <the obvious thing>. It's <the real thing>:
1. <step/pillar — with a number or concrete noun>
2. ...
3. ...

[6 BENEFIT BEATS] <2–4 short lines translating mechanism → outcome the reader feels.>

[7 THESIS CALLBACK] <Restate the ownable claim from the hook, sharpened.>

[8 QUESTION] So: <a question that makes the reader audit their own work>?

[CTA] ⭐ <repo url>   |   <demo/hub link> ↓
```

---

## 4. Pre-publish checklist (the "grader")

Score the draft against this before posting. Anything unchecked is a revise.

- [ ] **Hook is one line** and survives the "would a busy dev stop?" test.
- [ ] **Every number is true** and traceable to the fact base / repo.
- [ ] **No hype adjectives** carrying the weight ("revolutionary", "game-changing",
      "blazing-fast"). Cut them; let specifics carry it.
- [ ] **Second person** dominates; it's about the reader, not us.
- [ ] **One idea per line**, generous whitespace, scannable in 5 seconds.
- [ ] **Risk reversal present** (open-source / local / free tier) near the top.
- [ ] **A numbered mechanism** ("N steps / N pillars") — the rigor signal.
- [ ] **An ownable thesis** appears in the hook AND the callback.
- [ ] **One engagement question** that provokes self-audit (not "thoughts?").
- [ ] **Exactly one primary CTA** (don't split attention).
- [ ] **Claims are honest about maturity** — market the proven core; don't imply
      deferred/frontier work is shipped.
- [ ] **Channel fit** — length and shape match LinkedIn vs X vs Show HN.

---

## 5. Anti-patterns (don't)

- Leading with "I'm excited to announce…" (the reader isn't, yet).
- A wall of paragraphs; specs without benefits; feature soup with no thesis.
- Unverifiable superlatives ("the best", "fastest ever").
- Multiple CTAs competing for the click.
- Overclaiming maturity — the fastest way to lose a technical audience.
- Burying the differentiator below the fold.

---

## 6. Fact base (claims we can defend — keep current)

Source: repo `README.md`, `AGENTS.md`, test suite. Update when the repo changes.

- **Thesis:** "Stop generating tools. Start engineering loops." Software that
  improves itself instead of being generated once and frozen.
- **What it does:** point it at an API/service or a codebase → builds an
  agent-native CLI → grades it against reality → refactors until the grade stops
  climbing → reports how it got there.
- **Reality-grounded judging:** an independent referee (CLI-Judge) grades on **5
  dimensions, A–F**, against real captured payloads — never the model grading
  itself.
- **Degradation-proof:** multi-signal convergence — stops at the first of **4
  signals**: target grade · plateau · budget (iteration/token/wall-clock) ·
  safety block.
- **Safety is terminal:** an unsafe tool never ships, regardless of score.
- **Compounding:** every accepted fix becomes a regression test, so a solved
  problem never returns.
- **Integrity:** maker ≠ checker is enforced; a converged result is a *claim*
  until a human confirms (anti-cognitive-surrender gate).
- **Architecture:** wrap-don't-fork — it drives **4 existing tools**
  (CLI-Printing-Press, CLI-Anything, CLI-Judge, compound-engineering) around one
  closed loop; the novel surface is the controller + memory + convergence policy.
- **Local-first:** runs on your machine; every run/iteration/grade/learning in
  local SQLite.
- **Proven:** loop dynamics validated against recorded verdicts and a real
  referee; **286 tests** green on Python 3.11–3.13.
- **Honest maturity line:** the convergence/refine loop is proven; the
  fully-agentic generate frontier (CLI-Anything generation, Go service lane) has
  remaining live work — market the loop, not a finished "autopilot for anything".
- **Links:** repo `github.com/wjlgatech/loop-engineering-anything` · live hub
  `wjlgatech.github.io/loop-engineering-anything`.

---

## 7. How to run a launch (the loop)

1. **Pick the channel** → open the matching asset (`linkedin-launch.md`,
   `x-thread.md`, `show-hn.md`).
2. **Refresh the fact base** (§6) against the current repo.
3. **Draft** from the template (§3).
4. **Grade** against the checklist (§4) — revise until it passes.
5. **Ship** it.
6. **Compound:** add an entry to `dogfood-log.md` — hypothesis, what you changed
   vs. last time, and (after posting) the result. That learning seeds the next
   iteration. This is the step most teams skip; it's the whole edge.
