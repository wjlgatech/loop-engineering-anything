# ToolingJudge — discrimination proof (U3)

The factory's tooling half was blocked because nothing graded *generated* tooling.
`ToolingJudge` (`src/loopeng/adapters/tooling_judge.py`) is that referee —
**deterministic, no LLM**, so a grade is cheap, reproducible, and cannot be gamed
by a persuasive description. A grader is only worth shipping if it discriminates;
here is the evidence (real runs, 2026-07-19).

## Real skills (observed grades)

| Skill | Grade | Score | Note |
|---|---|---|---|
| `skills/loop-anything` (this repo) | **A** | 92 | well-formed; only dock: a pure-instruction skill references no verifiable script |
| `~/.claude/skills/benchmark` | **B** | 80 | references slash-pathed files that don't resolve from the skill dir |

## Discrimination on controlled inputs (from `tests/test_tooling_judge.py`)

| Input | Grade | Why |
|---|---|---|
| faithful, safe skill (real script that compiles) | **A** | structure + fidelity + safety all pass |
| no `SKILL.md` | **F** | not a skill |
| no YAML frontmatter | **F** | unloadable by any harness (hard gate) |
| references a script it never shipped | **↓ fidelity** | honest "vaporware" fixture |
| ships a script that fails to compile | **↓ fidelity** | "fails to compile" fixture |
| frontmatter `name` ≠ directory | **flagged** | faithfulness fixture |
| contains `rm -rf /` | **F** | safety gate is terminal (KTD5) |
| hardcoded `sk-…` secret | **F (unsafe)** | secret scan |

## Dimensions (weighted; measured-only, no fake pass)

- **structure** (30) — loadable `SKILL.md` + valid frontmatter (`name`, real `description`).
- **fidelity** (40) — name matches dir · every slash-pathed reference exists · referenced `.py` compiles.
- **safety** (30, terminal) — no hard-unsafe command / hardcoded secret; a hit ⇒ `safety_ok=False` ⇒ grade capped at F.

Two hard gates cap at F regardless of score: an **unsafe** artifact and an
**unloadable** one (no frontmatter). Reproduce: `pytest tests/test_tooling_judge.py`.

## What this unblocks

The `tooling-skill` domain (`src/loopeng/domains/tooling.py`) binds this judge, so
the loop controller can now **grade an existing skill and drive a refiner toward
Grade A** — the same refine-only path the software-codebase lane uses. The
remaining net-new work is U4: a Factory that *generates* the skill (keyed off the
repo's knowledge graph) so the loop can generate→grade→converge tooling end to end.
