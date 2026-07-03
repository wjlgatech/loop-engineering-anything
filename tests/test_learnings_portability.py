"""Learnings portability tests (plan 2026-07-02 U1): export/import the corpus.

The corpus must survive a laptop: export -> commit -> import on another machine
reproduces the reuse behavior, idempotently, through the single sanitized write
path, with redaction available for corpora that cross a sharing boundary.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from loopeng.cli import main
from loopeng.memory.portability import (
    IMPORT_RUN_STATUS,
    dump_jsonl,
    export_learnings,
    import_learnings,
    parse_jsonl,
)
from loopeng.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "a.db")
    yield s
    s.close()


@pytest.fixture
def other(tmp_path):
    s = MemoryStore(tmp_path / "b.db")
    yield s
    s.close()


def _seed(store, target="targetA", lane="service", summary="pin the framework version"):
    run = store.create_run(target, lane, "g", "2026-07-02T00:00:00Z")
    store.record_learning(run, None, summary, regression_test_ref="tests/test_x.py", grade_delta=2.0)
    return run


# ----- export ---------------------------------------------------------------


def test_export_carries_run_context_and_is_stable(store):
    _seed(store)
    records = export_learnings(store)
    assert records == [
        {
            "target": "targetA",
            "lane": "service",
            "summary": "pin the framework version",
            "regression_test_ref": "tests/test_x.py",
            "grade_delta": 2.0,
        }
    ]
    # Stable serialization: sorted keys, one object per line -> diff-able.
    line = dump_jsonl(records).splitlines()[0]
    assert list(json.loads(line)) == sorted(json.loads(line))


def test_export_target_filter(store):
    _seed(store, target="targetA", summary="a-lesson")
    _seed(store, target="targetB", summary="b-lesson")
    assert [r["summary"] for r in export_learnings(store, target="targetA")] == ["a-lesson"]


def test_export_redact_strips_target_specifics(store):
    _seed(store, summary="timeout fix worked on https://api.example.com for run 0123456789abcdef")
    rec = export_learnings(store, redact=True)[0]
    assert "api.example.com" not in rec["summary"]
    assert "0123456789abcdef" not in rec["summary"]
    assert "<redacted>" in rec["summary"]


# ----- import ---------------------------------------------------------------


def test_roundtrip_reproduces_reuse_on_fresh_store(store, other):
    _seed(store)
    result = import_learnings(other, export_learnings(store), started="2026-07-02T01:00:00Z")
    assert (result.imported, result.skipped) == (1, 0)
    # The reuse read path sees the imported learning exactly like a recorded one.
    assert other.prior_learnings(target="targetA") == ["pin the framework version"]


def test_import_is_idempotent(store, other):
    _seed(store)
    corpus = export_learnings(store)
    import_learnings(other, corpus, started="2026-07-02T01:00:00Z")
    again = import_learnings(other, corpus, started="2026-07-02T02:00:00Z")
    assert (again.imported, again.skipped) == (0, 1)
    assert len(other.learnings_with_context()) == 1


def test_import_sanitizes_through_the_single_write_path(other):
    hostile = [{"target": "t", "lane": "service", "summary": "do `rm -rf /`; $(whoami)\x00 bad"}]
    import_learnings(other, hostile, started="2026-07-02T01:00:00Z")
    stored = other.learnings_with_context()[0]["summary"]
    for bad in ("`", "$", ";", "\x00"):
        assert bad not in stored


def test_import_dedupes_against_sanitized_form(other):
    """A record differing only by scrubbed metachars collides with what's stored."""
    import_learnings(
        other, [{"target": "t", "summary": "lesson one"}], started="2026-07-02T01:00:00Z"
    )
    variant = [{"target": "t", "summary": "lesson `one`"}]  # sanitizes to "lesson one"
    result = import_learnings(other, variant, started="2026-07-02T02:00:00Z")
    assert (result.imported, result.skipped) == (0, 1)


def test_import_anchors_to_one_synthetic_run_per_target_lane(other):
    corpus = [
        {"target": "t1", "lane": "service", "summary": "s1"},
        {"target": "t1", "lane": "service", "summary": "s2"},
        {"target": "t2", "lane": "codebase", "summary": "s3"},
    ]
    import_learnings(other, corpus, started="2026-07-02T01:00:00Z")
    imported_runs = [r for r in other.list_runs() if r.status == IMPORT_RUN_STATUS]
    assert len(imported_runs) == 2  # one anchor per (target, lane), no iterations
    assert all(other.iterations(r.id) == [] for r in imported_runs)


def test_parse_jsonl_rejects_malformed_lines():
    with pytest.raises(ValueError, match="line 2"):
        parse_jsonl('{"target": "t", "summary": "ok"}\nnot-json\n')
    with pytest.raises(ValueError, match="line 1"):
        parse_jsonl('{"summary": "missing target"}\n')
    assert parse_jsonl("\n\n") == []


# ----- CLI glue -------------------------------------------------------------


def test_cli_export_import_roundtrip(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        s = MemoryStore("loopeng.db")  # the CLI's default store path
        _seed(s)
        s.close()

        out = runner.invoke(main, ["learnings", "export", "-o", "corpus.jsonl"])
        assert out.exit_code == 0, out.output
        assert "wrote 1 learning(s)" in out.output

        # Re-import into the same store: idempotent, nothing doubled.
        res = runner.invoke(main, ["learnings", "import", "corpus.jsonl"])
        assert res.exit_code == 0, res.output
        assert "imported 0, skipped 1" in res.output


def test_cli_import_rejects_bad_file(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        from pathlib import Path

        Path("bad.jsonl").write_text("not-json\n")
        res = runner.invoke(main, ["learnings", "import", "bad.jsonl"])
        assert res.exit_code != 0
        assert "line 1" in res.output
