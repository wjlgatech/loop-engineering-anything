"""Connector protocol + install/credential isolation boundary (U15, KTD8, R8).

A ``Connector`` is an actuator: a loop hands it a **structured payload** and it
acts on an external system. The contract that makes this safe to expose to a
self-improving loop is the isolation boundary, mirrored from the catalog adopter
(KTD7 in ``adopt.py``):

  - **Structured payloads only.** ``act(payload)`` takes a dict, never a string
    to interpolate. Any subprocess a connector spawns goes through ``run_tool``
    with ``shell=False`` and an args list, so a metacharacter-laden payload value
    can never reach a shell.
  - **Allowlisted environment.** Install and run children get ``minimal_env`` --
    a strict allowlist (``PATH``/``HOME``/...) plus only the credentials the spec
    declares -- so ambient secrets (``ANTHROPIC_API_KEY`` etc.) never leak into a
    connector's child process.
  - **Full-SHA pinning.** A connector that installs code pins by a full 40-char
    commit SHA; tags/branches are mutable and rejected.
  - **Throwaway install location outside the repo worktree.** Install lands in a
    dedicated ``--target`` dir *outside* the worktree, so a malicious
    post-install script cannot stage files a later Refiner would pick up.
  - **Credentials by name only.** Required credentials are declared by name and
    read from the environment; a missing one fails fast with the **name**, and a
    credential value is never logged.

Build-time code execution under a pinned SHA is an accepted residual risk
(recorded in the plan's Risks table).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..adapters.safety import ProcResult, minimal_env, run_tool, within_workspace

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
# A connector/package name is an identifier segment -- never a path or shell string.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


class ConnectorError(Exception):
    """Base class for connector boundary violations."""


class MissingCredentialError(ConnectorError):
    """A required credential env var is unset. Carries the NAME only, never a value."""


@dataclass(frozen=True)
class ConnectorResult:
    """Normalized outcome of a ``Connector.act`` call.

    ``ok`` is the single success signal; ``detail`` is a free-form structured echo
    (e.g. the canonicalized payload that was acted on) for the caller to inspect.
    Mirrors the ``ProcResult``/``AdoptResult`` "never raise for an operational
    failure" style: a connector returns ``ConnectorResult(ok=False)`` rather than
    leaking a stack trace.
    """

    ok: bool
    detail: dict = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ConnectorSpec:
    """How to install a connector that ships as external code (KTD8).

    ``sha`` MUST be a full 40-char hex commit SHA -- tags/branches are rejected.
    ``required_env`` names the credentials the connector legitimately needs; they
    are admitted to the child environment by name and gated by ``check_credentials``.
    """

    name: str  # connector/package name
    repo: str  # git URL to install from
    sha: str  # full 40-char commit SHA -- tags/branches rejected
    subdir: str = ""  # optional subdirectory within the repo
    required_env: tuple[str, ...] = ()  # credential names the connector needs


@runtime_checkable
class Connector(Protocol):
    """An actuator surface: declared capabilities + a structured ``act`` call.

    Implementations declare ``capabilities`` (the action verbs they support) and
    ``required_env`` (credential names they read from the environment). ``act``
    receives a **structured dict** -- never a string for shell interpolation -- and
    returns a normalized ``ConnectorResult``.
    """

    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> tuple[str, ...]: ...

    @property
    def required_env(self) -> tuple[str, ...]: ...

    def act(self, payload: dict) -> ConnectorResult: ...


def validate_spec(spec: ConnectorSpec) -> None:
    """Raise ``ValueError`` if the spec is unsafe to install. Pure -- no I/O."""
    if not _SAFE_NAME.match(spec.name or ""):
        raise ValueError(f"unsafe connector name: {spec.name!r}")
    if not _FULL_SHA.match(spec.sha or ""):
        raise ValueError(
            f"sha must be a full 40-char hex commit SHA, not a tag/branch: {spec.sha!r}"
        )
    if spec.subdir and (".." in spec.subdir or os.path.isabs(spec.subdir)):
        raise ValueError(f"unsafe connector subdir: {spec.subdir!r}")


def check_credentials(required_env: tuple[str, ...]) -> None:
    """Fail fast if a required credential env var is unset.

    Raises ``MissingCredentialError`` naming only the missing vars -- credential
    values are never read into the message (S-1, mirrors ``runner._check_credentials``).
    """
    missing = [name for name in required_env if not os.environ.get(name)]
    if missing:
        raise MissingCredentialError(
            f"missing required credential env vars: {', '.join(missing)}"
        )


def install_connector(spec: ConnectorSpec, install_root: str) -> ProcResult:
    """Install a connector's code into a throwaway dir **outside the repo worktree**.

    ``install_root`` MUST be outside the worktree (KTD8): a malicious post-install
    script then cannot stage files a later Refiner picks up. The install runs with
    ``run_tool`` (``shell=False``, args list) and ``minimal_env`` -- a strict
    allowlist that admits only the connector's declared ``required_env`` credentials
    plus minimal infrastructure, so ambient secrets never reach install-time code.

    Validates the spec (safe name + full-SHA) and the credential gate first. Never
    raises for an install failure -- it is normalized into ``ProcResult``.
    """
    validate_spec(spec)
    check_credentials(spec.required_env)

    worktree = os.getcwd()
    if within_workspace(install_root, worktree):
        raise ValueError(
            "connector install_root must be OUTSIDE the repo worktree (KTD8)"
        )
    os.makedirs(install_root, exist_ok=True)

    spec_url = f"git+{spec.repo}@{spec.sha}"
    if spec.subdir:
        spec_url += f"#subdirectory={spec.subdir}"

    # Pass declared credentials through by name; nothing else ambient is inherited.
    cred_env = {name: os.environ[name] for name in spec.required_env if name in os.environ}
    return run_tool(
        ["pip", "install", "--no-input", "--target", install_root, spec_url],
        cwd=install_root,
        timeout=20 * 60,
        env=minimal_env(extra=cred_env),
    )
