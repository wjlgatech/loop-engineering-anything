---
name: use-harnessx
description: Make harnessx agent-native — onboard an agent to harnessx's structure
  and key components from its knowledge graph before it touches the code.
---

# use-harnessx

Agent-native onboarding for **harnessx** (6317 nodes / 21715 edges), generated from its knowledge graph.
Goal: make the repo agent-native.

## Key components (from the KG)

- `uses`
- `calls`
- `contains`
- `method`
- `rationale_for`
- `imports_from`
- `inherits`
- `imports`

## Use

Run the onboarding helper first — it prints the repo's components from the bundled
KG summary (deterministic, no network):

```
python scripts/kg_query.py
```

Then read the named components above before making changes. This skill ships its
own `kg-summary.json`, so the helper works offline.
