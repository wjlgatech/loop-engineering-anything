# The run contract (`loop.yaml`)

**Problem.** Every input to a run — target, goal, lane, and ten budget knobs — existed
only as CLI flags. That makes a run unreviewable (no diff, no PR), unreproducible (the
invocation lives in someone's shell history), and impossible to attach to the proof pack
the run produces. A converged Grade A with no record of *what was asked for* is half an
artifact.

**Solution.** A contract file that is parsed, validated, and **compiled into primitives
the engine already enforces**.

```bash
loop-anything contract check docs/examples/loop.yaml            # validate; print the compiled plan
loop-anything run --contract docs/examples/loop.yaml            # run it
loop-anything contract evidence docs/examples/loop.yaml --run 12  # verify what it promised
```

See [`docs/examples/loop.yaml`](../examples/loop.yaml) for the annotated example (pinned
by a test, so it cannot rot).

---

## Three rules that keep it from becoming decoration

### 1. Compile, don't extend

A contract compiles into `config.Budget` and `config.Lane`. It adds no controller state
(KTD1) and cannot introduce a knob the loop does not read. `_execute_run` receives a
`Budget` — the same object the flag path builds — so there is exactly one code path.

### 2. Fail closed on anything unenforced

Unknown keys are a **parse error**, not a silent no-op:

```
loop.yaml.budget: unknown key(s) ['max_iteratons']; accepted: [...].
A contract may only declare what the engine enforces.
```

This is the rule that separates this from a config file. A typo'd `max_iteratons:`, or a
hopeful `safety: {forbidden: [delete_production_data]}` block, must not read as
"configured" when nothing consumes it — that is the false-green this engine exists to
prevent, dressed as governance.

Deliberately **not accepted**, for that reason:

| Rejected key | Why |
|---|---|
| `domain` | The `run` path routes by lane; `route()` has no forced-domain seam yet. Accepting it would silently do nothing. |
| `safety.forbidden` / `safety.require_human_approval` | Enforcement lives in `adapters/safety.py` (workspace jail, metachar rejection, `shell=False`) and `gate.yaml`. A second, unwired declaration site would be worse than none. |
| `evaluation.dimensions` / weights | The referee owns its rubric. A maker-authored file steering the grading is maker ≠ checker laundering. |
| `human_gate.require_two_person_review` | Not implemented (see the external eval, item 5). |

Each becomes accept-able the moment something enforces it — the error message is the
to-do list.

### 3. The gate is monotonic

`gate.require_human_confirm` may be omitted or `true`. **`false` is a parse error.**

A contract is caller-authored. `config.VerificationGate` deliberately exposes no
caller-settable bypass — only a CI-infrastructure env var, and never for `--scheduled`
runs — precisely so a scheduler cannot pre-confirm its own work. A contract that could
set `false` would hand that bypass straight back. A contract may only ever *tighten*.

---

## Evidence is a claim, not a promise

`evidence.required` names fields of the real proof pack (`proof.ProofPack.from_run`).
Only names a pack can actually carry are valid; anything else is a parse error. Then:

```bash
$ loop-anything contract evidence loop.yaml --run 12
  present  grade_trajectory
  MISSING  regression_tests
Error: run #12 is missing declared evidence: regression_tests
```

Exit code 1. A proof pack *omits* (never fakes) a field it has no source for, so a
missing item is a real gap between what the contract promised and what the run proved —
e.g. a converged run where `/ce-compound` recorded no regression test.

## Conflicts fail closed

Passing `--goal`, `--lane`, `--max-iterations`, or a positional `TARGET` alongside
`--contract` is an error rather than a silent precedence rule. Otherwise the committed
file would no longer describe the run it produced — which defeats the entire point of
having the file.

## Provenance

Shipped 2026-08-12 in response to an external architecture review
([external-eval-2026-08-12.md](external-eval-2026-08-12.md), items 1 and 7), built
narrower than proposed so it could not weaken items 2 and 5.
