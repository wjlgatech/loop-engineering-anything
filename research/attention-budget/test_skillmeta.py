"""Tests for the frontmatter reader — pinning the block-scalar bug it was written to fix.

Run: python3 -m pytest research/attention-budget/test_skillmeta.py -q
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from skillmeta import distinct, load_skills, parse_frontmatter  # noqa: E402


def test_plain_scalar():
    assert parse_frontmatter("---\nname: a\ndescription: hello there\n---\nbody\n")["description"] == "hello there"


def test_quoted_scalar_is_unquoted():
    assert parse_frontmatter('---\ndescription: "quoted desc"\n---\n')["description"] == "quoted desc"
    assert parse_frontmatter("---\ndescription: 'single'\n---\n")["description"] == "single"


def test_literal_block_scalar():
    """THE BUG: this used to return '|' -- a one-character description."""
    fm = parse_frontmatter("---\nname: x\ndescription: |\n  first line\n  second line\nversion: 1\n---\nbody\n")
    assert fm["description"] == "first line\nsecond line"
    assert fm["name"] == "x"
    assert fm["version"] == "1"  # the key AFTER the block is still parsed


def test_folded_block_scalar_joins_with_spaces():
    fm = parse_frontmatter("---\ndescription: >-\n  folded one\n  folded two\n---\n")
    assert fm["description"] == "folded one folded two"


def test_block_indicator_variants():
    for ind in ("|", "|-", "|+", ">", ">-", ">+", "|2", "|2-"):
        fm = parse_frontmatter(f"---\ndescription: {ind}\n  content here\n---\n")
        assert fm["description"] == "content here", ind


def test_no_frontmatter_is_empty_not_an_error():
    assert parse_frontmatter("# just markdown\n") == {}


def test_missing_description_is_absent_not_a_fake_value():
    assert "description" not in parse_frontmatter("---\nname: only\n---\n")


def test_phantom_is_reported_not_skipped(tmp_path):
    good = tmp_path / "good"
    good.mkdir()
    (good / "SKILL.md").write_text("---\nname: good\ndescription: fine\n---\n")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "SKILL.md").symlink_to(tmp_path / "nowhere" / "SKILL.md")

    readable, phantom = load_skills(tmp_path)
    assert [r["name"] for r in readable] == ["good"]
    assert len(phantom) == 1 and phantom[0]["dir"] == "bad"


def test_distinct_keeps_first_occurrence():
    recs = [{"name": "a", "desc": "first"}, {"name": "a", "desc": "second"}]
    assert distinct(recs)["a"]["desc"] == "first"


def test_real_library_has_no_indicator_only_descriptions():
    """Regression guard against the shipped bug: if the reader ever regresses, block-scalar
    skills reappear as 1-2 char descriptions. Skipped when no library is present."""
    root = pathlib.Path.home() / ".claude"
    if not root.is_dir():
        return
    readable, _ = load_skills(root)
    stubs = [r["name"] for r in readable if r["desc"] in ("|", "|-", ">", ">-", "|+", ">+")]
    assert not stubs, f"indicator-only descriptions leaked through: {stubs[:10]}"
