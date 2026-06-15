"""U1 manifest + registry tests (plan U1 Test scenarios)."""

from __future__ import annotations

import textwrap

import pytest

from loopeng.config import Lane
from loopeng.demos.manifest import ManifestError, from_dict, validate_target
from loopeng.demos.registry import Registry


def _valid(**over):
    base = {
        "id": "clinical-trials",
        "title": "ClinicalTrials.gov agent-native CLI",
        "domain": "Clinical trials & health",
        "target": "https://clinicaltrials.gov/api/v2",
        "lane": "service",
        "goal": "make trial search agent-native and raise to Grade A",
        "kind": "demo",
    }
    base.update(over)
    return base


def test_valid_manifest_loads_all_fields():
    m = from_dict(_valid(contributor="octocat", required_env=["X_TOKEN"]))
    assert m.id == "clinical-trials"
    assert m.lane is Lane.SERVICE
    assert m.runnable is True
    assert m.contributor == "octocat"
    assert m.required_env == ["X_TOKEN"]


def test_missing_required_field_errors_with_path():
    data = _valid()
    del data["goal"]
    with pytest.raises(ManifestError, match="goal"):
        from_dict(data)


def test_recipe_kind_is_not_runnable():
    m = from_dict(_valid(kind="recipe"))
    assert m.runnable is False


def test_service_target_must_be_https():
    with pytest.raises(ManifestError, match="https"):
        from_dict(_valid(target="http://example.com"))


def test_service_target_rejects_private_host_ssrf():
    with pytest.raises(ManifestError, match="SSRF"):
        from_dict(_valid(target="https://169.254.169.254/latest/meta-data/"))


def test_codebase_target_rejects_traversal():
    with pytest.raises(ManifestError, match="repo-relative"):
        from_dict(_valid(lane="codebase", target="../../etc/passwd"))


def test_secret_like_string_rejected():
    with pytest.raises(ManifestError, match="credential-like"):
        from_dict(_valid(goal="use token ghp_abcdefghijklmnopqrstuvwxyz0123"))


def test_validate_target_helper_accepts_clean_values():
    validate_target("https://api.example.com/v2", Lane.SERVICE)  # no raise
    validate_target("services/notes", Lane.CODEBASE)  # no raise


def _write(demos_dir, name, **over):
    import yaml

    (demos_dir / f"{name}.yaml").write_text(yaml.safe_dump(_valid(id=name, **over)))


def test_registry_rejects_duplicate_ids(tmp_path):
    (tmp_path / "a.yaml").write_text(__import__("yaml").safe_dump(_valid(id="dup")))
    (tmp_path / "b.yaml").write_text(__import__("yaml").safe_dump(_valid(id="dup")))
    with pytest.raises(ManifestError, match="duplicate"):
        Registry.load(tmp_path)


def test_registry_indexes_by_domain(tmp_path):
    _write(tmp_path, "legal", domain="Legal", target="https://sec.gov/x")
    _write(tmp_path, "clin", domain="Health", target="https://clinicaltrials.gov/x")
    _write(tmp_path, "trials2", domain="Health", target="https://clinicaltrials.gov/y")
    reg = Registry.load(tmp_path)
    by_domain = reg.by_domain()
    assert set(by_domain) == {"Legal", "Health"}
    assert len(by_domain["Health"]) == 2
