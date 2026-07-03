---
title: "feat: GitHub-for-PMs alignment — version the engine's own evolving artifacts"
type: feat
date: 2026-07-02
depth: survey
status: draft
external_research: load-bearing
sources:
  - https://www.news.aakashg.com/p/github-for-pms   # Aakash Gupta — thesis + free half (advanced workflows are paywalled)
  - https://github.com/wjlgatech/loop-engineering-anything  # this repo — the mechanized counterpart
---

# feat: GitHub-for-PMs alignment — version the engine's own evolving artifacts

## Summary

Aakash Gupta's *"GitHub for PMs"* argues that the artifacts people build with AI —
CLAUDE.md files, skills, eval criteria, prompts — drift and break silently, so they
should live under git with the full **pull → branch → edit → commit → push → PR →
merge** cycle, organized as three repos (private workspace / shared tools / per-project).
The paywalled half explicitly teases "Loop Engineering."

**Verdict: this repo is the mechanized version of that article.** What the article
prescribes as a manual human discipline, the loop already runs autonomously:
snapshot → refine → independent judge → keep-or-rollback → compound the learning.
The alignment is not "adopt the article's workflow" — it's the reverse: the article
names the one place the engine *doesn't* practice what it preaches, and the 10X is
to close that gap.

## Alignment map (article concept → existing mechanism)

| Article concept | loopeng mechanism | Status |
| --- | --- | --- |
| Branch → edit → PR review → merge/rollback (daily cycle) | `GitCheckpoint.snapshot()/restore()` (`loop/checkpoint.py:33-49`) + judge verdict in `_apply_outcome` (`loop/controller.py:265-303`) | ✅ automated, per-iteration |
| "Rollback to the last working prompt version" | regression → `git reset --hard <token>`; safety failure is terminal (`controller.py:203-210`) | ✅ stronger than the article (mechanical, not manual) |
| PR review by a teammate | independent CLI-Judge referee; maker≠checker is object identity | ✅ the reviewer is a referee, not vibes |
| Repo 2 "shared tools" (gstack, pm-skills) | `demos/` manifest catalog + `showcase/` hub + `docs/recipes/` | ✅ exists, provenance-badged |
| Repo 3 "per-project isolation" | per-run git worktrees (`autonomous/parallel.py:82-102`) | ✅ |
| Repo 1 "workspace that syncs across machines" | **`loopeng.db` — gitignored SQLite** (`memory/store.py`) | ❌ **the gap** |
| "Eval criteria evolve, keep their history" | rubric is *code* (`spec/rubric.py`), versioned only via source git; criteria not data | ⚠️ deliberate (determinism), revisit later |

## The shared disease

The engine's compounding memory — the `learnings` table (`memory/schema.sql:31-38`:
sanitized summary, `regression_test_ref`, `grade_delta`) — lives in a **gitignored,
machine-local SQLite file**. That is precisely the article's pain applied to
ourselves: unversioned, unreviewable, unsyncable, lost on machine failure, and
impossible to share as a "Repo 2" asset. The flywheel proved reuse compounds
(`flywheel/ablation.py`); the compounded asset itself has no version control.

## Units (ranked; U1 is the 10X)

### U1 — Learnings portability: `loop-anything learnings export / import`

Make the learning corpus a first-class versioned artifact:

- `learnings export [--target T] [--redact] -o learnings/<target>.jsonl` — dump the
  `learnings` table (and referenced regression-test refs) to committed, diff-able
  JSONL. `--redact` reuses the existing cross-target redaction
  (`store.prior_learnings` path) so a corpus can be shared publicly (article's
  Repo-2 tier) without leaking target-specific tokens.
- `learnings import <file>` — merge into the local store, idempotent
  (dedupe on content hash), **sanitize-on-write preserved** (`store.record_learning`
  stays the single write path).

Payoff: learnings become PR-reviewable ("here's what the loop learned this week"
as a diff), machine-portable, and shareable across users — the flywheel's
compounding survives the laptop. Smallest blast radius: pure store I/O + one CLI
group; zero loop-invariant changes.

### U2 — Loop-as-PR: emit the run as a pull request

Today the loop commits checkpoints onto whatever branch it's on. Add an opt-in
`--pr` mode: run on a generated branch, and on convergence open a PR whose body is
the proof report (grade trajectory, per-dimension diff, learnings compounded,
rollbacks). Human merge becomes the article's step 7 — and the README menu's
"PR lifecycle" row stops being aspirational. Depends on nothing in U1.

### U3 — `pm-workspace` loop recipe (docs/recipes/)

Point the loop at the article's artifact class itself: a repo of CLAUDE.md +
skills + eval criteria. `spec/rubric.py` already grades Markdown deterministically
(completeness / testability / consistency / scope / grounding) — a workspace's
skills are specs. Per repo convention this ships as an **illustrative recipe**
until a live `demo record` run earns `live_verified`.

## Deferred / rejected

- **Eval-criteria-as-data with version history** — the deterministic code-rubric is
  load-bearing (0-variance grading; `flywheel/oracle.py` exists precisely to stop
  rubric gaming). Making criteria mutable data reopens that attack surface.
  Revisit only with the downstream oracle as the gate.
- **Adopting the article's manual 3-repo discipline** — rejected; the engine's
  worktrees + demos hub already cover tiers 2–3, and U1 covers tier 1.
- **Paywalled workflows** (skill rollback, CLAUDE.md pruning, autoresearch tracking,
  eval versioning) — unverified content; U1/U3 reconstruct the two that matter from
  first principles rather than trusting a summary of text we couldn't read.

## Constraints

- Sequenced **after** `feat/design-fitness` lands — U1 touches `memory/store.py`
  and `cli.py`, both in that plan's blast radius.
- No change to the seven loop invariants; export/import never becomes a second
  write path around `record_learning`'s sanitization.
- Doc-sync policy applies: U1/U2 are feature code → CHANGELOG + README + agent
  guide in the same PR.
