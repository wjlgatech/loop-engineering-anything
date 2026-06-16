"""Demo manifest: load, schema-validate, and semantically validate (U1).

Beyond JSON Schema (structure), the loader enforces the security rules the
schema can't express (doc-review findings):
  - service-lane targets must be https with a non-private/link-local host (SSRF)
  - codebase-lane targets must be repo-relative with no `..` (path traversal)
  - no manifest string may contain a credential-like value (no secrets in git)
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import jsonschema
import yaml

from ..config import Lane

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "demos" / "SCHEMA.json"

# Credential-like patterns rejected from any committed manifest/fixture string.
# Committed proof-pack payload fixtures pass through this scan too, so the set is
# broadened beyond the original five (security finding) to cover bearer/JWT,
# cloud, and other common token shapes. A maintained scanner (gitleaks/detect-
# secrets) as a CI gate is the deferred follow-up; this is the in-process guard.
_SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                  # AWS access key id
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),              # GitHub PAT
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),        # other GitHub token kinds
    re.compile(r"sk-[A-Za-z0-9-]{20,}"),              # OpenAI / Anthropic (sk-ant-) keys
    re.compile(r"sk_live_[A-Za-z0-9]{20,}"),          # Stripe live key
    re.compile(r"hf_[A-Za-z0-9]{20,}"),               # HuggingFace token
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),     # PEM private key
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),      # Slack token
    re.compile(r"\"private_key_id\"\s*:"),            # GCP service-account JSON
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"),  # bearer token / JWT in a header
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
]


class ManifestError(ValueError):
    """Raised when a manifest is structurally or semantically invalid."""


@dataclass
class Manifest:
    id: str
    title: str
    domain: str
    target: str
    lane: Lane
    goal: str
    kind: str  # "demo" | "recipe"
    contributor: str | None = None
    required_env: list[str] = field(default_factory=list)
    exit_criteria: dict = field(default_factory=dict)
    result_ref: str | None = None

    @property
    def runnable(self) -> bool:
        return self.kind == "demo"


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text())


def _is_private_host(host: str) -> bool:
    if host in ("localhost", "", "0.0.0.0"):  # noqa: S104 - detection, not binding
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # a hostname; DNS-time SSRF is out of scope for static validation
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def validate_target(target: str, lane: Lane) -> None:
    """Raise ManifestError if the target is unsafe for its lane."""
    if lane is Lane.SERVICE:
        parsed = urlparse(target)
        if parsed.scheme != "https":
            raise ManifestError(f"service target must be an https URL: {target!r}")
        if _is_private_host(parsed.hostname or ""):
            raise ManifestError(f"service target host is private/link-local (SSRF): {target!r}")
    else:  # codebase
        if target.startswith(("/", "~")) or ".." in Path(target).parts:
            raise ManifestError(f"codebase target must be repo-relative without '..': {target!r}")


def _scan_for_secrets(values: list[str]) -> None:
    for value in values:
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                raise ManifestError("manifest contains a credential-like string; use required_env instead")


def from_dict(data: dict) -> Manifest:
    """Validate a raw dict against the schema + security rules and build a Manifest."""
    try:
        jsonschema.validate(data, _load_schema())
    except jsonschema.ValidationError as exc:
        field_path = ".".join(str(p) for p in exc.absolute_path) or "(root)"
        raise ManifestError(f"manifest invalid at {field_path}: {exc.message}") from exc

    lane = Lane(data["lane"])
    validate_target(data["target"], lane)
    _scan_for_secrets([str(v) for v in data.values() if isinstance(v, str)])

    return Manifest(
        id=data["id"],
        title=data["title"],
        domain=data["domain"],
        target=data["target"],
        lane=lane,
        goal=data["goal"],
        kind=data["kind"],
        contributor=data.get("contributor"),
        required_env=list(data.get("required_env", [])),
        exit_criteria=data.get("exit_criteria", {}),
        result_ref=data.get("result_ref"),
    )


def load_manifest(path: str | Path) -> Manifest:
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ManifestError(f"manifest is not a mapping: {path}")
    return from_dict(data)
