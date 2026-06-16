# Show HN

> HN rewards plain, technical, non-marketed language and honesty about maturity.
> Strip the LinkedIn cadence; lead with what it is and what's proven.

## Title

Show HN: Loop-engineering-anything – drive any tool up a grade scale until it converges

## First comment (the "what it is" body)

Most AI tooling generates a CLI once and freezes it — there's no closed loop
between "it exists" and "it's actually good." This is the controller, memory, and
convergence policy that wire four existing tools into a closed feedback loop:
route → generate → judge → refactor → re-judge → compound.

What's interesting (and what I'd want feedback on):

- **Quality comes from an independent referee, not the model.** CLI-Judge grades
  the tool on 5 dimensions (A–F) against real captured payloads. The controller
  only ever reads that verdict — it never inspects code patterns to decide
  quality. maker ≠ checker is enforced as a precondition (the refiner and the
  judge must be distinct objects).

- **Multi-signal convergence, so it can't degrade.** The loop stops at the first
  of: target grade, plateau (no gain over N), budget (iteration/token/wall-clock),
  or a safety block. A refactor that doesn't raise the grade is rolled back to the
  prior git checkpoint. A safety failure is a terminal state — the tool never
  ships.

- **It compounds.** Every accepted fix is recorded as a learning + a regression
  test, so a solved problem doesn't come back. There's a local SQLite memory that
  enables cross-run queries (trend, plateau, recurring failures).

- **Wrap, don't fork.** It drives CLI-Printing-Press, CLI-Anything, CLI-Judge,
  and the compound-engineering plugin behind adapters; the controller depends only
  on protocols, so the loop dynamics are testable against recorded verdicts with
  no live tool required.

Honesty on maturity: the convergence/refine loop is the proven part — validated
against recorded verdicts and a real installed referee, 286 tests on Python
3.11–3.13. The fully-agentic generate frontier (CLI-Anything generation, the
Go-based service lane, a full agentic generate+refine e2e) still has live work in
progress; the repo is explicit about that and ships unverified demos as
"illustrative" until a real run is recorded.

Repo: https://github.com/wjlgatech/loop-engineering-anything
Demo hub: https://wjlgatech.github.io/loop-engineering-anything/

Happy to go deep on the convergence policy or the maker≠checker integrity gate.
