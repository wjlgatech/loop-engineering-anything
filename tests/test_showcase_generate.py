"""U3 showcase generator tests (plan U3 Test scenarios)."""

from __future__ import annotations

import yaml

from loopeng.demos.registry import Registry
from loopeng.showcase.generate import render_catalog, safe_url


def _manifest(**over):
    base = {
        "id": "clinical-trials",
        "title": "ClinicalTrials CLI",
        "domain": "Health",
        "target": "https://clinicaltrials.gov/api/v2",
        "lane": "service",
        "goal": "agent-native trial search",
        "kind": "demo",
    }
    base.update(over)
    return base


def _result(**over):
    base = {
        "demo_id": "clinical-trials",
        "source": "live_verified",
        "grade_trajectory": ["C", "B", "A"],
        "final_grade": "A",
        "convergence_status": "converged",
        "report_ref": "clinical-trials.report.md",
    }
    base.update(over)
    return base


def _registry(tmp_path, manifests, results=None):
    import json

    for m in manifests:
        (tmp_path / f"{m['id']}.yaml").write_text(yaml.safe_dump(m))
    if results:
        rdir = tmp_path / "results"
        rdir.mkdir()
        for r in results:
            (rdir / f"{r['demo_id']}.json").write_text(json.dumps(r))
    return Registry.load(tmp_path)


def test_live_verified_card_shows_trajectory_and_verified_badge(tmp_path):
    reg = _registry(tmp_path, [_manifest(contributor="octocat", result_ref="clinical-trials.json")], [_result()])
    html = render_catalog(reg)
    assert "C &rarr; B &rarr; A" in html
    assert "verified run" in html
    assert "demos/results/clinical-trials.report.md" in html


def test_illustrative_card_is_badged_not_verified(tmp_path):
    reg = _registry(
        tmp_path,
        [_manifest(result_ref="clinical-trials.json")],
        [_result(source="illustrative")],
    )
    html = render_catalog(reg)
    assert "prov illustrative" in html
    assert "prov verified" not in html  # the verified badge must not appear


def test_script_in_title_is_escaped(tmp_path):
    reg = _registry(tmp_path, [_manifest(title="<script>alert(1)</script>")])
    html = render_catalog(reg)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_javascript_url_rejected_in_report_ref():
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("//evil.com") is None
    assert safe_url("data:text/html,x") is None
    assert safe_url("https://ok.com/r") == "https://ok.com/r"
    assert safe_url("demos/results/x.report.md") == "demos/results/x.report.md"


def test_contributor_html_is_escaped_in_leaderboard(tmp_path):
    # contributor pattern is enforced by schema, but the generator must still escape defensively.
    reg = _registry(tmp_path, [_manifest(contributor="octocat")])
    html = render_catalog(reg)
    assert "@octocat" in html


def test_blocked_safety_badge_renders(tmp_path):
    reg = _registry(
        tmp_path,
        [_manifest(result_ref="clinical-trials.json")],
        [_result(source="illustrative", grade_trajectory=["C"], final_grade="C", convergence_status="blocked_safety")],
    )
    html = render_catalog(reg)
    assert "conv blocked_safety" in html


def test_draft_card_when_no_result(tmp_path):
    reg = _registry(tmp_path, [_manifest()])  # no result_ref
    html = render_catalog(reg)
    assert "not yet run" in html
    assert "draft" in html


def test_recipe_renders_in_recipes_lane(tmp_path):
    reg = _registry(tmp_path, [_manifest(id="quant", kind="recipe", domain="Quant")])
    html = render_catalog(reg)
    assert "Loop recipes" in html
    assert "docs/recipes/quant.md" in html
    assert "not runnable yet" in html


def test_empty_registry_renders_hero_not_blank(tmp_path):
    reg = Registry.load(tmp_path)
    html = render_catalog(reg)
    assert "No demos yet" in html
    assert "Tools that grade themselves better" in html


def test_output_has_no_external_assets(tmp_path):
    reg = _registry(tmp_path, [_manifest()])
    html = render_catalog(reg)
    assert "http://" not in html  # no external asset URLs
    assert "src=\"http" not in html
    assert "aria-live" in html  # a11y: live region present
