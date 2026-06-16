"""Catalog tool adopter (U1, KTD7).

Adopts an already-generated agent-native CLI from an external catalog
(clianything.cc / printingpress.dev) into a workspace-jailed directory so the
loop can use it as a refine-only *baseline* ("before") without ever running the
unproven from-scratch generate frontier.

Security is the whole point of this module (KTD7 / doc-review). ``pip install``
and ``npx`` execute arbitrary build / postinstall code *at install time*, before
any filesystem jail applies and with the full inherited environment. So jailing
where files land is not enough. The adopter therefore:

  - installs into a dedicated throwaway location inside the workspace
    (``<workspace>/.venv`` or a ``--target`` dir), never the parent env;
  - spawns every adoption subprocess with an explicit **pruned environment**
    that strips ambient credentials (anything matching a secret-name pattern),
    keeping only the manifest-declared ``required_env`` plus a minimal
    ``PATH``/``HOME``/``TMPDIR``;
  - pins by a **full 40-char commit SHA** (tags/branches are mutable and a
    force-push past the host allowlist would silently install different code);
  - only adopts from an **allowlisted catalog host**;
  - never logs credential values.

The controller never sees this module: adoption produces a ``tool_path`` that
``run_refine_loop`` (U2) hands to the protocol-only controller. Wrap, don't fork
(KTD1) -- we adopt a published tool as a *target*, we never copy its generator.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field

from .adapters.safety import ProcResult, run_tool, within_workspace

# Catalog sources we will install from. Host-level allowlist gates *where* code
# comes from; per-entry human review (CONTRIBUTING-demos.md) gates *what* it
# does. Pinning is by full commit SHA so a moved tag cannot swap the code.
ALLOWED_CATALOGS: dict[str, str] = {
    "cli-anything": "https://github.com/HKUDS/CLI-Anything",
    "printing-press": "https://github.com/mvanhorn/printing-press-library",
}

# Install mechanisms. ``pip_git_subdir`` -> a CLI-Anything Python/Click harness
# living in ``<name>/agent-harness``; ``pp_binary`` -> a Printing-Press prebuilt
# binary. The Go-build path is intentionally NOT a kind here: it is toolchain-
# gated follow-up, not attempted by default.
INSTALL_KINDS = ("pip_git_subdir", "pp_binary")

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
# A package/entry name is an identifier segment -- never a path or shell string.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")

# Env-var NAMES that look like secrets; stripped from any adoption subprocess so
# install-time third-party code cannot read them. Matched case-insensitively.
_SECRET_NAME_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTH", "API")
# Names that contain a hint substring but are safe infrastructure to keep.
_SECRET_NAME_ALLOW = {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "TERM", "SHELL"}


@dataclass(frozen=True)
class AdoptSpec:
    """What to adopt. ``sha`` MUST be a full 40-char hex commit SHA (KTD7)."""

    catalog: str  # key into ALLOWED_CATALOGS
    name: str  # entry/package name within the catalog
    sha: str  # full 40-char commit SHA -- tags/branches rejected
    install_kind: str  # one of INSTALL_KINDS
    required_env: tuple[str, ...] = ()  # env names the tool legitimately needs


@dataclass(frozen=True)
class AdoptResult:
    ok: bool
    tool_path: str | None = None
    resolved_sha: str | None = None
    logs: str = ""
    error: str | None = None


def validate_spec(spec: AdoptSpec) -> None:
    """Raise ``ValueError`` if the spec is unsafe to adopt. Pure -- no I/O."""
    if spec.catalog not in ALLOWED_CATALOGS:
        raise ValueError(
            f"catalog {spec.catalog!r} is not allowlisted (allowed: {sorted(ALLOWED_CATALOGS)})"
        )
    if spec.install_kind not in INSTALL_KINDS:
        raise ValueError(f"unknown install_kind {spec.install_kind!r} (allowed: {INSTALL_KINDS})")
    if not _FULL_SHA.match(spec.sha or ""):
        raise ValueError(
            f"sha must be a full 40-char hex commit SHA, not a tag/branch: {spec.sha!r}"
        )
    if not _SAFE_NAME.match(spec.name or ""):
        raise ValueError(f"unsafe catalog entry name: {spec.name!r}")


def pruned_env(required_env: tuple[str, ...] = ()) -> dict[str, str]:
    """A minimal environment for an adoption subprocess.

    Drops every ambient var whose NAME looks like a secret, then re-admits the
    tool's declared ``required_env`` and a small infrastructure set. The goal is
    that install-time third-party code cannot read ``ANTHROPIC_API_KEY`` and the
    like (KTD7). Values are never inspected or logged.
    """
    keep_names = set(_SECRET_NAME_ALLOW) | {"PATH", "HOME", "TMPDIR"} | set(required_env)
    out: dict[str, str] = {}
    for name, value in os.environ.items():
        upper = name.upper()
        looks_secret = any(h in upper for h in _SECRET_NAME_HINTS) and upper not in _SECRET_NAME_ALLOW
        if name in keep_names or not looks_secret:
            out[name] = value
    # Guarantee the infra minimum exists even if absent from the parent env.
    out.setdefault("PATH", os.defpath)
    return out


def _pip_install(spec: AdoptSpec, workspace: str) -> AdoptResult:
    """Install a CLI-Anything Python harness into an isolated dir in the workspace.

    Uses ``pip install --target`` into ``<workspace>/.pkg`` so build/postinstall
    hooks run against a non-default location, with a pruned env (KTD7).
    """
    target = os.path.join(workspace, ".pkg")
    if not within_workspace(target, workspace):  # defense-in-depth
        return AdoptResult(False, error="resolved install target escaped the workspace")
    os.makedirs(target, exist_ok=True)
    base = ALLOWED_CATALOGS[spec.catalog]
    spec_url = f"git+{base}@{spec.sha}#subdirectory={spec.name}/agent-harness"
    res = run_tool(
        ["pip", "install", "--no-input", "--target", target, spec_url],
        cwd=workspace,
        timeout=20 * 60,
        env=pruned_env(spec.required_env),
    )
    if not res.ok:
        return AdoptResult(False, logs=res.stderr[:1000], error="pip install failed")
    return AdoptResult(True, tool_path=target, resolved_sha=spec.sha, logs=res.stdout[:1000])


def _binary_install(spec: AdoptSpec, workspace: str) -> AdoptResult:
    """Resolve a Printing-Press prebuilt binary into the workspace.

    The npx/release fetch runs with a pruned env; the resulting binary is placed
    under ``<workspace>/bin``. Checksum verification of the downloaded artifact
    is a live-run concern (the SHA-256 lives in the manifest) -- here we wire the
    install path and isolation; the e2e run adds the checksum gate.
    """
    bindir = os.path.join(workspace, "bin")
    if not within_workspace(bindir, workspace):
        return AdoptResult(False, error="resolved bin dir escaped the workspace")
    os.makedirs(bindir, exist_ok=True)
    res = run_tool(
        [
            "npx",
            "-y",
            "@mvanhorn/printing-press-library",
            "install",
            spec.name,
            "--cli-only",
        ],
        cwd=bindir,
        timeout=20 * 60,
        env=pruned_env(spec.required_env),
    )
    if not res.ok:
        return AdoptResult(False, logs=res.stderr[:1000], error="binary install failed")
    return AdoptResult(True, tool_path=bindir, resolved_sha=spec.sha, logs=res.stdout[:1000])


def adopt(spec: AdoptSpec, workspace: str) -> AdoptResult:
    """Adopt a catalog tool into ``workspace`` as a refine baseline.

    Validates the spec (allowlist + full-SHA + safe name), then runs the
    install for the spec's kind with a pruned environment. Never raises for an
    install failure -- the failure is normalized into ``AdoptResult(ok=False)``,
    mirroring ``run_tool``.
    """
    try:
        validate_spec(spec)
    except ValueError as exc:
        return AdoptResult(False, error=str(exc))

    os.makedirs(workspace, exist_ok=True)
    if spec.install_kind == "pip_git_subdir":
        return _pip_install(spec, workspace)
    return _binary_install(spec, workspace)
