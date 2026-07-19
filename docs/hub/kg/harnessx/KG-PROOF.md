# Knowledge graph — harnessx (deterministic AST, no LLM)

- Files ingested: **584**
- Nodes: **6317**  ·  Edges: **21715**
- Edge confidence: {'EXTRACTED': 6497, 'INFERRED': 15218} — EXTRACTED = literal AST facts (imports/contains/inherits); INFERRED = heuristic edges (e.g. `uses`, `rationale_for`), honestly tagged so a consumer can trust the difference.
- HTML viz rendered: False (graph exceeds the vis.js node cap — graph.json is the artifact)

## Node types
- code: 4584
- rationale: 1733

## Edge types
- uses: 12683
- calls: 2535
- contains: 2504
- method: 1670
- rationale_for: 1568
- imports_from: 436
- inherits: 241
- imports: 78

## Highest-degree nodes (structural hubs)
- `events_message` — degree 551
- `processor_multihookprocessor` — degree 532
- `events_modelresponseevent` — degree 378
- `harness_harnessconfig` — degree 372
- `events_stepstartevent` — degree 358
- `events_taskendevent` — degree 357
- `events_taskstartevent` — degree 354
- `events_toolresultevent` — degree 352
- `journal_harnessjournal` — degree 341
- `events_beforemodelevent` — degree 313
