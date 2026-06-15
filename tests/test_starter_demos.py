"""U4 starter-demo tests — validate the shipped registry (plan U4 Test scenarios)."""

from __future__ import annotations

from loopeng.demos.registry import Registry
from loopeng.showcase.generate import render_catalog

ARTICLE_DOMAINS = {
    "Interactive spec / PR lifecycle",
    "Legal & compliance",
    "Clinical trials & health",
    "Biotech & drug discovery",
    "Quant asset management",
    "VC & angel investing",
    "Complex software architecture",
    "Education & curriculum",
    "Smart-grid energy",
    "Supply chain & logistics",
}


def _reg():
    return Registry.load()  # the real repo demos/ directory


def test_all_manifests_and_fixtures_validate():
    reg = _reg()
    for m in reg.manifests.values():
        reg.result_for(m)  # loads + schema-validates any fixture
    assert len(reg.demos()) == 10
    assert len(reg.recipes()) >= 1


def test_every_starter_fixture_is_illustrative():
    # The honesty guarantee: no shipped card claims a live_verified run it never had.
    reg = _reg()
    for m in reg.demos():
        result = reg.result_for(m)
        assert result is not None, f"{m.id} has no result fixture"
        assert result.source == "illustrative", f"{m.id} must ship as illustrative"


def test_domains_in_article_set_and_credentials_declared():
    reg = _reg()
    for m in reg.demos():
        assert m.domain in ARTICLE_DOMAINS, f"{m.id} domain {m.domain!r} not in article set"
    # pr-lifecycle (GitHub) is the credentialed target and must declare its env var.
    pr = reg.manifests["pr-lifecycle"]
    assert "GITHUB_TOKEN" in pr.required_env


def test_showcase_renders_all_with_recipe_lane():
    reg = _reg()
    html = render_catalog(reg)
    assert "Loop recipes" in html
    for m in reg.recipes():
        assert f"docs/recipes/{m.id}.md" in html


def test_blocked_safety_demo_present_for_badge_coverage():
    # supply-chain ships a blocked_safety result so the safety badge is exercised.
    reg = _reg()
    result = reg.result_for(reg.manifests["supply-chain"])
    assert result.convergence_status == "blocked_safety"
