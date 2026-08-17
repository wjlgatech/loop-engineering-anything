# Attention as a budget — applying and extending `@skills`

R&D against **arXiv:2608.12610**, *"@skills: Attention is all you have"* (Yin, Li, Shi, Zhang,
Seong, Wang — SylphAI / UT Austin, **12 Aug 2026**) and its reference implementation
[SylphAI-Inc/atskills](https://github.com/SylphAI-Inc/atskills) (MIT, TypeScript).

## What the paper argues

Installing a skill bundles three separable things — **content, persistence, and
auto-triggering** — and only the last one needs the system prompt. So:

> "56,804 skills to be reachable while fewer than ten are resident."

Its generalization, stated in its own conclusion, is the mandate for everything in this
directory:

> "The principle generalizes past skills: resident context is a budget; spend it only on
> what must fire implicitly, and deliver everything else at the point of use, where
> attention is highest."

## The honest status of its headline number

The paper claims a budget of "fewer than a hundred reliable auto-trigger slots per agent."
It is explicit that this is **not measured**:

> "Our central quantity, the number of reliable auto-trigger slots, is bounded by argument
> and by the literature rather than measured by us"

and it names the missing experiment as future work:

> "The measurements this argument invites are trigger reliability as a function of
> installed-skill count"

Engagement context, measured 13 Aug 2026: the preprint is **one day old**, the repo has
**26 stars**, and no community discussion was findable. This is a fresh argument, not an
adopted standard. Treat the framing as valuable and the digit as open.

---

## 1. Applied — `residency_audit.py`

Audits a real library against the three-tier model. Run on this operator's own machine:

| measure | value |
|---|---|
| `SKILL.md` entries | **221** (204 readable, 17 phantom) |
| distinct skill names | **176** |
| paper's argued reliable-slot bound | 100 |
| **over budget by** | **1.76x** |
| resident index (name + description) | 62,010 chars (~15,502 tokens) |
| every body, if resident | 2,954,435 chars (~738,608 tokens) |
| **content-to-index ratio** | **47.6x** |

Four failure classes the paper predicts, all present:

- **PHANTOM — 17.** Every one is a dangling symlink into a `gstack/` path that no longer
  holds them. The protocol says a client "MUST refuse to `:install` it loudly rather than
  write a line that silently loads nothing." These fail *silently*: the capability is gone
  and nothing says so. The failure is not wasted attention — it is **absence with no signal**.
- **DUPLICATE — 25 names installed more than once** (`access` ×3, `configure` ×3,
  `living-knowledge` ×3). The local form of the corpus-wide collisions the paper measures.
- **OVERLONG — 130 of 176** descriptions (74%) exceed the protocol's ~120-char guidance;
  the worst is **11.6x** it. The description *is* the trigger signal, so length is spent attention.
- **UNTRIGGERED — 1** of 176 carries no description at all, so it cannot feed a trigger index.

The tool **measures and proposes; it never mutates.** Which capabilities deserve residency is
operator judgement, and a script that silently re-tiered a library would be making exactly
the unreviewable change the protocol exists to prevent.

Full report: [`AUDIT.md`](./AUDIT.md).

### A correction, recorded rather than quietly fixed

The first version of this audit reported a resident index of 34,120 chars and a ratio of
86.6x, with 72 overlong descriptions. **Those numbers were wrong.** The reader used
`^description:\s*(.*)$`, which captures the *indicator* of a YAML block scalar — so every
skill written as `description: |` was measured as having a **one-character** description.
The parser never failed; it returned a plausible wrong value, which is the precise failure
class this audit exists to report. Fixed in [`skillmeta.py`](./skillmeta.py) and pinned by
[`test_skillmeta.py`](./test_skillmeta.py), including a regression guard that fails if any
indicator-only description ever reappears in a real library.

## 2. R&D area 1 — measuring the paper's unmeasured quantity

[`trigger_reliability.py`](./trigger_reliability.py) runs the experiment the paper names as
future work, against a **real** 176-skill corpus rather than a synthetic one.

Design: a menu of N skill descriptions always containing one target, plus a first-person
user request the target is meant to serve; score top-1 selection; sweep N.

- **subject** (picks the skill): `openai/gpt-oss-120b` via Groq
- **generator** (writes the probes): Gemini 3.6 Flash, falling back to Claude Haiku — a
  *different family* from the subject, so the request wording is not authored by the model
  that has to route it. Maker ≠ checker applied to the data.
- **Declared bias:** probes are generated *from* each target's own description, so trigger
  wording leaks into the request. Every trial is therefore **easier than reality**, making
  the result an **optimistic upper bound** — whatever degradation appears, the real
  degradation is at least that large.
- **Honesty rules:** a failed API call is recorded as an error and **excluded from the
  denominator**, never scored as a model miss (that would manufacture the paper's
  conclusion); every response is disk-cached so re-runs are reproducible, not re-sampled;
  an N with fewer than 8 usable trials reports "insufficient data" rather than a number.

Two measured transport facts, both of the kind that silently corrupt this class of
experiment:

1. Groq sits behind Cloudflare, which **403s (error 1010) on urllib's default User-Agent**
   while accepting the identical payload from curl.
2. `gpt-oss-120b` bills reasoning tokens to `max_tokens`, so a small cap returns an
   **empty `content`** — a false "the model said nothing" that is really a budget bug.

Results land in `results.json`.

## 3. R&D area 2 — the same principle, applied to tool schemas

Already shipping, and measurable from this session: the harness listed **~190 MCP tool
names with their schemas withheld** — "Their schemas are NOT loaded… Use ToolSearch" —
i.e. tier-3 residency for the *name*, tier-1 on-demand fetch for the *schema*. Exactly the
protocol, one layer down, for tools instead of skills.

Sampled schema cost (n=2, the two tools actually loaded this session: `WebFetch`,
`WebSearch`): ~250 tokens each. Extrapolated, ~190 resident schemas would cost ~47k tokens
versus ~1.5k for names alone — a **~30x** ratio, independently in the same order as the
**47.6x** measured for skills. Marked as an estimate: n=2 is a sample, not a census.

## 4. R&D area 3 — the same principle, applied to instructions

| resident on every session | chars | ~tokens |
|---|---:|---:|
| global `CLAUDE.md` | 4,184 | 1,046 |
| Projects-root `CLAUDE.md` | 13,861 | 3,465 |
| `~/.anyagent/backbone.md` | 1,097 | 274 |
| `~/.anyagent/playbooks.md` (index only) | 172 | 43 |
| **total** | **19,314** | **4,828** |

Plus **63 per-project `CLAUDE.md` files**, 506,788 chars (~127k tokens) in aggregate, median
5,686, largest 39,890.

Two findings:

1. **The Projects-root `CLAUDE.md` is 3.3x the global one**, and most of it is a *venture
   directory* — reference material answering "which repo does what". That is tier-1 content
   (read on demand) wearing tier-3 clothes (resident always). It is the single largest
   misfiled residency on this machine.
2. **The pattern was already here before the paper existed.** `backbone.md` (1,097 chars,
   always resident) sits beside `playbooks.md` (**172 chars**, an index), and the anyagent
   skill states the rule explicitly: *"The table below is an **index**… On a trigger match,
   READ that file; otherwise do not carry it."* That is the paper's tier-3/tier-1 split,
   hand-rolled, independently. The protocol's contribution is not the idea — it is giving
   the idea an **address**.

---

## Prior art, across four windows

**🏺 300 years.** What survived is not any particular index but the **separation of a cheap
resident finding-aid from expensive non-resident content**, plus a **computed address** so
content can move without breaking the pointer. Panizzi's rules (1841) → Cutter's *Objects of
the Catalogue* (1876) → Paris Principles (1961) → IFLA's ICP (2016), which opens: *"This
statement builds on the great cataloguing traditions of the world,³"* — footnote 3 being
Cutter. Cutter, 1876: *"the convenience of the public must not be sacrificed to brevity"*;
ICP 2016, principle #1: *"Convenience of the user."* 140 years apart, same rule.
Dewey's **relative location** (1876) — the address is *computed*, not assigned — now serves
200,000+ libraries in 135+ countries. Graveyard: **fixed-location shelving** (every
acquisition reclassified its neighbours) and Otlet's **Mundaneum** (15.6M cards, defunded
1934, partly destroyed 1940 — the vision survived, the artifact did not).

**🕰 30 years.** Every survivor separates a **cheap validated pointer** from expensive
content: HTTP caching (born 1997, re-specified as **RFC 9111, STD 98, June 2022** — an ETag
is a resident pointer you can validate without moving the content), git content-addressing
(2005 — which `@skills:gh:owner/repo/path` simply borrows), CDN edge caching (1998). The
loudest corpse is **HTML5 AppCache** (removed from Chrome 95, Oct 2021), which died
specifically of a **declarative manifest that fixed residency in advance** — so the paper's
"no manifest, no lockfile, no registration" is not minimalist taste, it is the lesson of a
documented death. Second corpse: **Intel Optane** (market life 2017–2022; Intel wrote off
**$559M**), an entire new tier of the memory hierarchy killed by economics, not physics —
and The Register's requiem of 29 July 2026 calls it *"Intel's KV cache killer that could
have eased the RAM price crunch."*

**A gap worth naming:** virtual memory (1962), demand paging, and Denning's working-set
model (1968) are **58–67 years old** — older than the 30-year window, younger than the
300-year window's 75-year multi-generational floor. The field's canonical answers to "what
stays resident" fall in a blind spot between the two research windows, and are *not* yet
generationally proven.

**🌗 30 months.** `SKILL.md` crossed demo→default: Agent Skills announced 16 Oct 2025, open
standard 18 Dec 2025, adopted by Microsoft in VS Code/GitHub, ~40 compatible products by
June 2026; MCP donated to the Linux Foundation 9 Dec 2025.

**📰 30 days.** The paper is one day old, 26 stars, no findable discussion. Fresh argument,
not an adopted standard.

---

## Reproducing

```bash
python3 research/attention-budget/residency_audit.py --out AUDIT.md     # no network, no keys
GROQ_API_KEY=… GEMINI_API_KEY=… python3 research/attention-budget/trigger_reliability.py
```

The audit is offline and deterministic. The experiment caches every response under
`.cache/`, so a second run costs nothing and returns the same numbers.
