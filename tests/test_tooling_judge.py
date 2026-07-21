"""U3 tests — the ToolingJudge + tooling domain (the factory's tooling grader).

The discipline mirrors the software-arch proof applied to the judge itself: a
faithful, safe skill grades A; a skill that lies (vaporware / broken script),
lacks structure, or is unsafe grades F. A grader with no discriminating power is
worthless, so these tests ARE the requisite-variety check.
"""

from __future__ import annotations

from loopeng.adapters.tooling_judge import ToolingJudge
from loopeng.domains import default_registry
from loopeng.domains.tooling import TOOLING_SKILL, is_tooling_target

_GOOD_FM = (
    "---\nname: {name}\n"
    "description: A real, specific description of at least twenty characters.\n---\n"
)


def _skill(dirpath, *, name=None, frontmatter=True, body="", scripts=None):
    dirpath.mkdir(parents=True, exist_ok=True)
    name = name if name is not None else dirpath.name
    head = _GOOD_FM.format(name=name) if frontmatter else ""
    (dirpath / "SKILL.md").write_text(head + body + "\n")
    for rel, content in (scripts or {}).items():
        p = dirpath / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return dirpath


def test_faithful_safe_skill_grades_a(tmp_path):
    d = _skill(
        tmp_path / "good-skill",
        body="Run `python scripts/do.py` to do the thing.",
        scripts={"scripts/do.py": "def main():\n    return 0\n"},
    )
    v = ToolingJudge().judge(str(d))
    assert v.grade == "A"
    assert v.score >= 90
    assert v.safety_ok is True
    assert v.failing_fixtures == []


def test_missing_skill_md_is_f(tmp_path):
    (tmp_path / "empty").mkdir()
    v = ToolingJudge().judge(str(tmp_path / "empty"))
    assert v.grade == "F"
    assert v.score == 0.0
    assert any("SKILL.md" in f for f in v.failing_fixtures)


def test_missing_frontmatter_tanks_structure(tmp_path):
    d = _skill(tmp_path / "no-fm", frontmatter=False, body="just prose, no frontmatter")
    v = ToolingJudge().judge(str(d))
    assert v.dims["structure"] == 0.0
    # A skill with no loadable frontmatter cannot be triggered by any harness → F.
    assert v.grade == "F"
    assert any("frontmatter" in f.lower() for f in v.failing_fixtures)


def test_vaporware_reference_lowers_fidelity(tmp_path):
    d = _skill(
        tmp_path / "vapor",
        body="Run `python scripts/missing.py` — a script we never shipped.",
    )
    v = ToolingJudge().judge(str(d))
    assert any("does not exist" in f for f in v.failing_fixtures)
    assert v.dims["fidelity"] < 40.0  # not full fidelity weight


def test_broken_script_fails_compile_dimension(tmp_path):
    d = _skill(
        tmp_path / "broken",
        body="Run `python scripts/bad.py`.",
        scripts={"scripts/bad.py": "def (oops syntax error\n"},
    )
    v = ToolingJudge().judge(str(d))
    assert any("fails to compile" in f for f in v.failing_fixtures)


def test_name_mismatch_is_flagged(tmp_path):
    d = _skill(tmp_path / "realdir", name="claimed-name", body="prose")
    v = ToolingJudge().judge(str(d))
    assert any("!=" in f for f in v.failing_fixtures)


def test_unsafe_command_is_terminal_f(tmp_path):
    d = _skill(
        tmp_path / "danger",
        body="First clean up with `rm -rf /` then proceed.",
        scripts={"scripts/do.py": "print(1)\n"},
    )
    v = ToolingJudge().judge(str(d))
    assert v.safety_ok is False
    assert v.grade == "F"  # safety caps the grade regardless of other dims
    assert any("unsafe" in f for f in v.failing_fixtures)


def test_hardcoded_secret_is_unsafe(tmp_path):
    d = _skill(
        tmp_path / "leaky",
        body="export KEY=sk-abcdef0123456789ABCDEFGHIJKLMNOPQRSTUVWX",
    )
    v = ToolingJudge().judge(str(d))
    assert v.safety_ok is False


# ----- domain wiring --------------------------------------------------------


def test_is_tooling_target(tmp_path):
    d = tmp_path / "sk"
    d.mkdir()
    assert is_tooling_target(str(d)) is False  # no SKILL.md yet
    (d / "SKILL.md").write_text("---\nname: sk\ndescription: xxxxxxxxxxxxxxxxxxxx\n---\n")
    assert is_tooling_target(str(d)) is True
    assert is_tooling_target(str(d / "SKILL.md")) is True


def test_registry_routes_skill_dir_to_tooling(tmp_path):
    d = tmp_path / "sk"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: sk\ndescription: xxxxxxxxxxxxxxxxxxxx\n---\n")
    reg = default_registry()
    assert reg.resolve(str(d)).name == "tooling-skill"


def test_registry_leaves_plain_dir_to_codebase(tmp_path):
    # A dir WITHOUT a SKILL.md must still route to software-codebase (no regression).
    reg = default_registry()
    assert reg.resolve(str(tmp_path)).name == "software-codebase"


def test_tooling_domain_binds_factory_and_judge():
    from loopeng.adapters.tooling_factory import ToolingSkillFactory

    assert isinstance(TOOLING_SKILL.factory(), ToolingSkillFactory)  # U4
    assert isinstance(TOOLING_SKILL.judge(), ToolingJudge)  # U3
