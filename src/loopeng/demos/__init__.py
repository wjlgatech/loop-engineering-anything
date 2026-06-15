"""Community demo manifests, result fixtures, and registry (U1)."""

from .manifest import Manifest, ManifestError, load_manifest, validate_target
from .registry import Registry
from .result import Result, load_result

__all__ = [
    "Manifest",
    "ManifestError",
    "load_manifest",
    "validate_target",
    "Registry",
    "Result",
    "load_result",
]
