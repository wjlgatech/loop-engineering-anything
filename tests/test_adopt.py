"""U1 catalog-adopter tests (mocked subprocess).

Covers the KTD7 security surface: full-SHA pinning, host allowlist, safe-name
validation, workspace isolation, credential-pruned env, and normalized failure.
"""

from __future__ import annotations

import pytest

from loopeng import adopt
from loopeng.adapters.safety import ProcResult, within_workspace

GOOD_SHA = "a" * 40


def _spec(**kw):
    base = dict(
        catalog="cli-anything",
        name="cli-anything-wiremock",
        sha=GOOD_SHA,
        install_kind="pip_git_subdir",
    )
    base.update(kw)
    return adopt.AdoptSpec(**base)


# ----- validation (pure, no I/O) -----------------------------------------


def test_rejects_non_allowlisted_catalog():
    with pytest.raises(ValueError, match="allowlisted"):
        adopt.validate_spec(_spec(catalog="evil-host"))


def test_rejects_tag_or_branch_ref():
    with pytest.raises(ValueError, match="40-char"):
        adopt.validate_spec(_spec(sha="v0.1.0"))
    with pytest.raises(ValueError, match="40-char"):
        adopt.validate_spec(_spec(sha="main"))


def test_rejects_unsafe_name():
    with pytest.raises(ValueError, match="unsafe"):
        adopt.validate_spec(_spec(name="../etc/passwd"))
    with pytest.raises(ValueError, match="unsafe"):
        adopt.validate_spec(_spec(name="foo; rm -rf ~"))


def test_rejects_unknown_install_kind():
    with pytest.raises(ValueError, match="install_kind"):
        adopt.validate_spec(_spec(install_kind="curl_bash"))


def test_good_spec_validates():
    adopt.validate_spec(_spec())  # no raise


# ----- pruned env (KTD7) --------------------------------------------------


def test_pruned_env_strips_ambient_credentials(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
    monkeypatch.setenv("MY_PASSWORD", "hunter2")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = adopt.pruned_env()
    assert "ANTHROPIC_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert "MY_PASSWORD" not in env
    assert env["PATH"] == "/usr/bin"


def test_pruned_env_readmits_declared_required_env(monkeypatch):
    monkeypatch.setenv("WIREMOCK_API_KEY", "needed")
    env = adopt.pruned_env(required_env=("WIREMOCK_API_KEY",))
    assert env["WIREMOCK_API_KEY"] == "needed"


# ----- install path (mocked run_tool) -------------------------------------


def test_pip_install_targets_workspace_and_prunes_env(monkeypatch, tmp_path):
    captured = {}

    def fake_run(args, *, cwd=None, timeout=None, env=None):
        captured["args"] = args
        captured["env"] = env
        return ProcResult(0, "Installed", "")

    monkeypatch.setattr(adopt, "run_tool", fake_run)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")

    res = adopt.adopt(_spec(), str(tmp_path))
    assert res.ok is True
    assert within_workspace(res.tool_path, str(tmp_path))
    assert res.resolved_sha == GOOD_SHA
    # install went into an isolated --target dir, not the parent env
    assert "--target" in captured["args"]
    assert any(str(tmp_path) in a for a in captured["args"])
    # the pinned SHA (not a tag) is in the install URL
    assert any(GOOD_SHA in a for a in captured["args"])
    # ambient credential is not visible to the install subprocess
    assert "ANTHROPIC_API_KEY" not in captured["env"]


def test_binary_install_happy_path(monkeypatch, tmp_path):
    monkeypatch.setattr(adopt, "run_tool", lambda *a, **k: ProcResult(0, "ok", ""))
    res = adopt.adopt(_spec(catalog="printing-press", name="arxiv", install_kind="pp_binary"), str(tmp_path))
    assert res.ok is True
    assert within_workspace(res.tool_path, str(tmp_path))


def test_install_failure_is_normalized_not_raised(monkeypatch, tmp_path):
    monkeypatch.setattr(adopt, "run_tool", lambda *a, **k: ProcResult(1, "", "boom"))
    res = adopt.adopt(_spec(), str(tmp_path))
    assert res.ok is False
    assert res.tool_path is None
    assert "boom" in res.logs


def test_bad_spec_returns_error_result_not_raise(tmp_path):
    res = adopt.adopt(_spec(sha="not-a-sha"), str(tmp_path))
    assert res.ok is False
    assert "40-char" in (res.error or "")
