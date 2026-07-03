"""Learnings portability (plan 2026-07-02 U1): the corpus as a versioned artifact.

The ``learnings`` table is the engine's compounding memory, but ``loopeng.db``
is gitignored and machine-local -- the exact "workspace drift" failure the loop
prevents for its targets, applied to itself. This module closes that gap:

- ``export_learnings`` renders the corpus as stable, diff-able JSONL a repo can
  commit and a PR can review; ``redact=True`` strips target-specific tokens
  (URLs/paths/long ids) via the same ``redact_specifics`` used for cross-target
  reuse, so a corpus can be shared publicly without leaking one target's details.
- ``import_learnings`` merges a corpus back through
  ``MemoryStore.record_learning`` -- the single sanitize-on-write path (flywheel
  R4) -- so an imported line can no more forge prompt structure than a recorded
  one. Idempotent: re-importing the same file inserts nothing.

Imported learnings attach to one synthetic run per (target, lane) with status
``imported`` so ``prior_learnings``'s runs-join scoping keeps working. A
synthetic run carries no iterations, so trend/plateau/reuse-stats queries
(which key off iterations) are unaffected.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..util.sanitize import redact_specifics, sanitize_text
from .store import MemoryStore

IMPORT_RUN_STATUS = "imported"
_FIELDS = ("target", "lane", "summary", "regression_test_ref", "grade_delta")


def export_learnings(
    store: MemoryStore, *, target: str | None = None, redact: bool = False
) -> list[dict]:
    """The learning corpus as portable records (optionally one target's, redacted)."""
    records = []
    for row in store.learnings_with_context(target):
        rec = {k: row[k] for k in _FIELDS}
        if redact:
            rec["summary"] = redact_specifics(rec["summary"])
        records.append(rec)
    return records


def dump_jsonl(records: list[dict]) -> str:
    """One sorted-key JSON object per line -- stable output => reviewable diffs."""
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)


def parse_jsonl(text: str) -> list[dict]:
    """Parse a corpus file; a malformed line names its line number, never passes silently."""
    records = []
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"line {i}: not valid JSON ({e.msg})") from e
        if not isinstance(rec, dict) or not rec.get("target") or not rec.get("summary"):
            raise ValueError(f"line {i}: a learning record needs 'target' and 'summary'")
        records.append(rec)
    return records


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: int


def import_learnings(
    store: MemoryStore, records: list[dict], *, started: str
) -> ImportResult:
    """Merge RECORDS into STORE, idempotently, through the sanitized write path.

    Dedupe key is the *sanitized* summary + target + regression_test_ref, so a
    record always collides with what ``record_learning`` would actually store.
    """
    existing = {
        (r["target"], r["summary"], r["regression_test_ref"])
        for r in store.learnings_with_context()
    }
    run_ids: dict[tuple[str, str], int] = {}
    imported = skipped = 0
    for rec in records:
        target = str(rec["target"])
        lane = str(rec.get("lane") or "unknown")
        ref = rec.get("regression_test_ref")
        clean = sanitize_text(str(rec["summary"]))
        key = (target, clean, ref)
        if key in existing:
            skipped += 1
            continue
        run_key = (target, lane)
        if run_key not in run_ids:
            run_ids[run_key] = _import_run_id(store, target, lane, started)
        store.record_learning(
            run_ids[run_key],
            None,
            clean,
            regression_test_ref=ref,
            grade_delta=rec.get("grade_delta"),
        )
        existing.add(key)
        imported += 1
    return ImportResult(imported=imported, skipped=skipped)


def _import_run_id(store: MemoryStore, target: str, lane: str, started: str) -> int:
    """Find-or-create the synthetic anchor run for imported (TARGET, LANE) learnings."""
    for run in store.list_runs():
        if run.target == target and run.lane == lane and run.status == IMPORT_RUN_STATUS:
            return run.id
    run_id = store.create_run(target, lane, "imported learning corpus", started)
    store.finish_run(run_id, IMPORT_RUN_STATUS, None)
    return run_id
