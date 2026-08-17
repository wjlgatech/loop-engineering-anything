# Skill residency audit

Library: `/Users/jialiang.wu/.claude`

## The budget

- `SKILL.md` entries found: **221** (204 readable, 17 phantom)
- Distinct skill names: **176**
- Paper's conservative reliable-slot bound: **100**
- Over budget by: **1.76x**

- Resident index (name + description): **34,120 chars** (~8,530 tokens)
- Every body, if all were resident: **2,954,435 chars** (~738,608 tokens)
- Content-to-index ratio: **86.6x** — this is the paper's thesis as a single number: the index costs ~1/86 of the content.

## PHANTOM — holds a name, loads nothing

**17 entries.** The protocol says a client MUST refuse such an entry *loudly*. These fail silently instead: the capability is simply absent, and nothing tells you.

- `benchmark-models` → `/Users/jialiang.wu/Documents/Projects/gstack/benchmark-models/SKILL.md`
- `context-restore` → `/Users/jialiang.wu/Documents/Projects/gstack/context-restore/SKILL.md`
- `context-save` → `/Users/jialiang.wu/Documents/Projects/gstack/context-save/SKILL.md`
- `document-generate` → `/Users/jialiang.wu/Documents/Projects/gstack/document-generate/SKILL.md`
- `ios-clean` → `/Users/jialiang.wu/Documents/Projects/gstack/ios-clean/SKILL.md`
- `ios-design-review` → `/Users/jialiang.wu/Documents/Projects/gstack/ios-design-review/SKILL.md`
- `ios-fix` → `/Users/jialiang.wu/Documents/Projects/gstack/ios-fix/SKILL.md`
- `ios-qa` → `/Users/jialiang.wu/Documents/Projects/gstack/ios-qa/SKILL.md`
- `ios-sync` → `/Users/jialiang.wu/Documents/Projects/gstack/ios-sync/SKILL.md`
- `landing-report` → `/Users/jialiang.wu/Documents/Projects/gstack/landing-report/SKILL.md`
- `make-pdf` → `/Users/jialiang.wu/Documents/Projects/gstack/make-pdf/SKILL.md`
- `pair-agent` → `/Users/jialiang.wu/Documents/Projects/gstack/pair-agent/SKILL.md`
- `plan-tune` → `/Users/jialiang.wu/Documents/Projects/gstack/plan-tune/SKILL.md`
- `scrape` → `/Users/jialiang.wu/Documents/Projects/gstack/scrape/SKILL.md`
- `setup-gbrain` → `/Users/jialiang.wu/Documents/Projects/gstack/setup-gbrain/SKILL.md`
- `skillify` → `/Users/jialiang.wu/Documents/Projects/gstack/skillify/SKILL.md`
- `sync-gbrain` → `/Users/jialiang.wu/Documents/Projects/gstack/sync-gbrain/SKILL.md`

## DUPLICATE — one capability, more than one slot

**25 names installed more than once.** Each extra copy is a slot spent on a capability already present — the local form of the name collisions the paper measures across the public corpus.

- `access` ×3
- `animate-anything` ×2
- `configure` ×3
- `copilotkit` ×2
- `dreammaketrue` ×2
- `enduser-webtest` ×2
- `free-llm` ×2
- `freellmapi` ×2
- `frontend-design` ×2
- `future-self` ×2
- `installable-web-app` ×2
- `knowledge-graph` ×2
- `knowledgefy` ×2
- `lavish` ×2
- `living-knowledge` ×3
- `living-repo` ×2
- `no-mistakes` ×2
- `open-gstack-browser` ×2
- `proactive-intervention` ×2
- `skill-creator` ×2

## OVERLONG — description past the protocol's ~120-char guidance

**72 of 176** exceed it. The description *is* the trigger signal, so every extra character is resident attention spent on one tenant of the index.

- `dreammaketrue` — 1394 chars (11.6x guidance)
- `free-llm` — 1173 chars (9.8x guidance)
- `knowledgefy` — 1074 chars (8.9x guidance)
- `living-repo` — 951 chars (7.9x guidance)
- `enduser-webtest` — 913 chars (7.6x guidance)
- `project-artifact` — 906 chars (7.5x guidance)
- `knowledge-graph` — 869 chars (7.2x guidance)
- `continual-learning-research` — 853 chars (7.1x guidance)
- `treehouse` — 786 chars (6.5x guidance)
- `no-mistakes` — 779 chars (6.5x guidance)
- `skillfy` — 775 chars (6.5x guidance)
- `freellmapi` — 774 chars (6.5x guidance)

## UNTRIGGERED — cannot feed a trigger index

None.

## Proposal

To reach the argued bound, **76 skills** must stop being resident. In @skills terms that is not deletion — it is demotion from tier 3 (auto-trigger) to tier 1 (addressed by path, read at the point of use). Ranked cheapest-first:

1. Remove the **17 phantom** entries. Zero capability lost — they already load nothing.
2. Collapse the **25 duplicated** names to one copy each.
3. Rewrite the **72 overlong** descriptions toward 120 chars. Same coverage, less resident spend.
4. Demote every skill that is only ever invoked *by name* (a slash command you type) out of the auto-trigger index. If you always ask for it explicitly, it never needed a trigger slot — that is the paper's central point, and it is the largest available win.

This tool does not apply any of the above. Which capabilities deserve residency is operator judgement, and a script that silently re-tiered a library would be making exactly the unreviewable change the protocol exists to prevent.
