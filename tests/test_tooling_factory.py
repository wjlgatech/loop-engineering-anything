"""U4 tests — the ToolingSkillFactory (generate skill from a KG) + generate→grade.

The proof the factory works is that its output passes the *independent* U3 judge:
a KG-keyed skill it generates grades A (structure + fidelity + safety), with no
post-hoc fixing. That is generate→grade composing, deterministically.
"""

from __future__ import annotations

import json
import os

from loopeng.adapters.tooling_factory import ToolingSkillFactory
from loopeng.adapters.tooling_judge import ToolingJudge

_KG = {
    "repo": "harnessx",
    "nodes": 6317,
    "edges": 21715,
    "edge_types": {"uses": 12683, "calls": 2535, "contains": 2504},
    "top_hubs": ["events_message", "processor_multihookprocessor", "harness_harnessconfig"],
}


def _write_kg(tmp_path):
    p = tmp_path / "kg-summary.json"
    p.write_text(json.dumps(_KG))
    return str(p)


def test_generate_produces_a_valid_skill(tmp_path):
    kg = _write_kg(tmp_path)
    out = tmp_path / "out"
    res = ToolingSkillFactory().generate(kg, "make harnessx agent-native", str(out))
    assert res.ok
    assert res.lane == "tooling"
    assert os.path.basename(res.tool_path) == "use-harnessx"
    assert os.path.isfile(os.path.join(res.tool_path, "SKILL.md"))
    assert os.path.isfile(os.path.join(res.tool_path, "scripts", "kg_query.py"))
    assert os.path.isfile(os.path.join(res.tool_path, "kg-summary.json"))
    assert res.manifest["source_repo"] == "harnessx"


def test_generated_skill_grades_a_on_the_u3_judge(tmp_path):
    kg = _write_kg(tmp_path)
    res = ToolingSkillFactory().generate(kg, "onboard", str(tmp_path / "out"))
    verdict = ToolingJudge().judge(res.tool_path)
    # generate -> grade, deterministically: a faithful, safe, loadable skill = A.
    assert verdict.grade == "A"
    assert verdict.safety_ok is True
    assert verdict.failing_fixtures == []


def test_generated_helper_actually_runs(tmp_path):
    import subprocess
    import sys

    kg = _write_kg(tmp_path)
    res = ToolingSkillFactory().generate(kg, "", str(tmp_path / "out"))
    helper = os.path.join(res.tool_path, "scripts", "kg_query.py")
    proc = subprocess.run([sys.executable, helper], capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    assert "harnessx" in proc.stdout
    assert "6317" in proc.stdout  # nodes count surfaced from the bundled summary


def test_generate_degrades_honestly_without_a_kg(tmp_path):
    # No KG summary: still produces a loadable, safe skill (thinner, but honest).
    res = ToolingSkillFactory().generate("some-repo", "goal", str(tmp_path / "out"))
    assert res.ok
    assert res.manifest["kg_summary_source"] is None
    verdict = ToolingJudge().judge(res.tool_path)
    assert verdict.safety_ok is True
    assert verdict.grade in {"A", "B"}  # loadable + faithful helper, no vaporware
