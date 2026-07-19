"""Build a real knowledge graph for a cited repo — deterministic, no LLM (U2 knowledge half).

Uses graphify's deterministic AST path (extract -> build -> export) to produce a
knowledge graph for a checked-out repo. Code-only, so it is near-free and
reproducible: no model calls, no API keys, no fabricated cluster labels. Emits
graph.json (+ HTML when under the viz cap) and a concise, honest proof report the
factory can record as its first live *knowledge* artifact.

Usage: build_repo_kg.py <repo_checkout_dir> <out_dir> <repo_label>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from graphify.build import build
from graphify.export import to_html, to_json
from graphify.extract import collect_files, extract


def main() -> int:
    repo_dir, out_dir, label = sys.argv[1], sys.argv[2], sys.argv[3]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = collect_files(Path(repo_dir))
    extraction = extract(files)  # deterministic tree-sitter AST, no LLM
    G = build([extraction])

    # Relativize source paths so the committed artifact is clean/portable
    # (strip the local clone dir; keep the repo-relative path). Handle the macOS
    # /tmp -> /private/tmp symlink: strip both the raw and resolved prefixes.
    prefixes = sorted({str(Path(repo_dir)), str(Path(repo_dir).resolve())}, key=len, reverse=True)

    def _relativize(d: dict) -> None:
        for k, v in list(d.items()):
            if isinstance(v, str):
                for clone in prefixes:
                    if clone in v:
                        d[k] = v.replace(clone, label)
                        break

    for _, d in G.nodes(data=True):
        _relativize(d)
    for _, _, d in G.edges(data=True):
        _relativize(d)

    communities: dict[int, list[str]] = {}  # no LLM clustering in the free path
    to_json(G, communities, str(out / "graph.json"))

    html_ok = False
    try:
        to_html(G, communities, str(out / "graph.html"))
        html_ok = True
    except ValueError as e:
        (out / "graph.html.skipped.txt").write_text(str(e))

    # Honest report generated FROM the graph (no fabricated semantics).
    node_types = Counter(d.get("file_type", "?") for _, d in G.nodes(data=True))
    edge_types = Counter(d.get("relation", d.get("type", "?")) for _, _, d in G.edges(data=True))
    conf = Counter(d.get("confidence", "EXTRACTED") for _, _, d in G.edges(data=True))
    degree = dict(G.degree())
    top = sorted(degree.items(), key=lambda kv: kv[1], reverse=True)[:10]

    summary = {
        "repo": label,
        "files_ingested": len(files),
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "node_types": dict(node_types.most_common()),
        "edge_types": dict(edge_types.most_common()),
        "edge_confidence": dict(conf),
        "html_rendered": html_ok,
    }
    (out / "kg-summary.json").write_text(json.dumps(summary, indent=2))

    lines = [
        f"# Knowledge graph — {label} (deterministic AST, no LLM)",
        "",
        f"- Files ingested: **{len(files)}**",
        f"- Nodes: **{G.number_of_nodes()}**  ·  Edges: **{G.number_of_edges()}**",
        f"- Edge confidence: {dict(conf)} — EXTRACTED = literal AST facts "
        "(imports/contains/inherits); INFERRED = heuristic edges (e.g. `uses`, "
        "`rationale_for`), honestly tagged so a consumer can trust the difference.",
        f"- HTML viz rendered: {html_ok}"
        + ("" if html_ok else " (graph exceeds the vis.js node cap — graph.json is the artifact)"),
        "",
        "## Node types",
        *[f"- {k}: {v}" for k, v in node_types.most_common()],
        "",
        "## Edge types",
        *[f"- {k}: {v}" for k, v in edge_types.most_common()],
        "",
        "## Highest-degree nodes (structural hubs)",
        *[f"- `{n}` — degree {d}" for n, d in top],
    ]
    (out / "KG-PROOF.md").write_text("\n".join(lines) + "\n")

    print(json.dumps(summary, indent=2))
    return 0 if G.number_of_nodes() > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
