# Pluggable refiner: the refine engine is not hardcoded to Claude

**Decision.** The `Refiner` is a protocol (`src/loopeng/adapters/base.py`), so the
loop does not depend on *what* drives the edits. Two bindings ship:
`ClaudeCodeRefiner` (`/ce-work` via `claude -p` — the documented "brain") and
`FallbackLLMRefiner` (any OpenAI-compatible endpoint with a free-tier fallback
chain). `demo proof --refiner claude|llm` selects between them; the controller is
unchanged either way.

**Why.** The headless `claude -p` refine quota was a hard blocker on running a
real before/after proof until 2026-07-01. Because the refiner is protocol-bound,
the quota is not a true dependency of the *loop* — only of one refiner binding.
`FallbackLLMRefiner` drives NVIDIA NIM → Groq → Gemini → local Ollama (the
`free-llm` standing fallback-chain policy) over stdlib `urllib`, so a genuine
refine run can happen today on a free backend with no Claude involvement.

**Safety.** The LLM refiner applies model output only as **jailed full-file
rewrites** — each target path must resolve `within_workspace`, and model output
is never executed as a shell command. A refine that fails to raise the grade is
rolled back by the existing `GitCheckpoint`, and CLI-Judge's safety gate still
catches unsafe *tool* behavior. The `--refiner llm` path uses a store-only
compounder (learnings recorded for the proof pack; no `/ce-compound` doc step).

**Identity note.** compound-engineering remains the *default* and the documented
brain; the LLM refiner is an explicit, opt-in alternative for quota-free or
offline runs — not a replacement of the project's thesis.

See `docs/solutions/refine-only-baseline.md`, `docs/solutions/p0-feasibility-gates.md`,
and the `free-llm` skill for the verified endpoints/model ids.
