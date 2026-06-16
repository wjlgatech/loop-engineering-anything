"""U4 starter-demo tests — validate the shipped registry (plan U4 Test scenarios)."""

from __future__ import annotations

from loopeng.demos.registry import Registry
from loopeng.showcase.generate import render_catalog

# Shipped domains. Two intentionally diverge from the article's grand labels to
# match their real targets honestly: Open-Meteo is weather (not a grid), OpenSky
# is aviation (not freight). Honest labels beat impressive ones.
SHIPPED_DOMAINS = {
    "Interactive spec / PR lifecycle",
    "Legal & compliance",
    "Clinical trials & health",
    "Biotech & drug discovery",
    "Quant asset management",
    "VC & angel investing",
    "Complex software architecture",
    "Education & curriculum",
    "Weather & forecasting",
    "Aviation tracking",
}


# Refine-loop proof targets (catalog-to-proof pipeline, U5): real catalog CLIs
# adopted as baselines. A distinct cohort from the 10 article-domain starters --
# they ship WITHOUT a fixture (draft) and earn a card only via a real `demo proof`.
PROOF_TARGET_IDS = {"arxiv", "hackernews", "wikipedia"}

# Graduated self-contained demos: recipes that became real, `live_verified` demos
# via an actual F->A loop run + `demo record` (a third cohort, distinct from the 10
# article starters and the catalog proof-targets). These legitimately ship verified.
GRADUATED_DEMO_IDS = {"automate-your-job", "factcli"}


def _reg():
    return Registry.load()  # the real repo demos/ directory


def _starters(reg):
    return [
        m for m in reg.demos()
        if m.id not in PROOF_TARGET_IDS and m.id not in GRADUATED_DEMO_IDS
    ]


def test_all_manifests_and_fixtures_validate():
    reg = _reg()
    for m in reg.manifests.values():
        reg.result_for(m)  # loads + schema-validates any fixture
    assert len(_starters(reg)) == 10
    assert len(reg.recipes()) >= 1


def test_every_starter_fixture_is_illustrative():
    # The honesty guarantee: no shipped starter card claims a live_verified run it never had.
    reg = _reg()
    for m in _starters(reg):
        result = reg.result_for(m)
        assert result is not None, f"{m.id} has no result fixture"
        assert result.source == "illustrative", f"{m.id} must ship as illustrative"


def test_proof_targets_are_draft_or_illustrative_never_unearned_verified():
    # No live run yet -> draft (no fixture) is the honest state; a proof target must
    # NEVER ship as live_verified without a recorded run (the honesty discipline).
    reg = _reg()
    for demo_id in PROOF_TARGET_IDS:
        assert demo_id in reg.manifests, f"{demo_id} manifest missing"
        result = reg.result_for(reg.manifests[demo_id])
        assert result is None or result.source != "live_verified", (
            f"{demo_id} must not be live_verified without a real run"
        )


def test_graduated_demo_is_live_verified():
    # The first recipe to graduate: automate-your-job earned a real, recorded run.
    reg = _reg()
    for demo_id in GRADUATED_DEMO_IDS:
        assert demo_id in reg.manifests, f"{demo_id} manifest missing"
        result = reg.result_for(reg.manifests[demo_id])
        assert result is not None, f"{demo_id} has no recorded result"
        assert result.source == "live_verified", f"{demo_id} must be live_verified (a real run)"
        assert result.final_grade == "A", f"{demo_id} recorded grade should be A"


def test_domains_match_shipped_set_and_credentials_declared():
    reg = _reg()
    for m in _starters(reg):
        assert m.domain in SHIPPED_DOMAINS, f"{m.id} domain {m.domain!r} not in shipped set"
    # pr-lifecycle (GitHub) is the credentialed target and must declare its env var.
    pr = reg.manifests["pr-lifecycle"]
    assert "GITHUB_TOKEN" in pr.required_env


def test_codebase_demo_targets_exist_on_disk():
    # software-arch / edu-curriculum point at real vendored repos, not placeholders.
    from pathlib import Path

    reg = _reg()
    repo_root = Path(reg.demos_dir).parent
    for demo_id in ("software-arch", "edu-curriculum"):
        target = reg.manifests[demo_id].target
        assert (repo_root / target).is_dir(), f"{demo_id} target {target!r} does not exist"


def test_showcase_renders_all_with_recipe_lane():
    reg = _reg()
    html = render_catalog(reg)
    assert "Loop recipes" in html
    for m in reg.recipes():
        assert f"docs/recipes/{m.id}.md" in html


