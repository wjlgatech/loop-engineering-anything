"""Demo registry (U1): discover, validate, index manifests; join to results."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .manifest import Manifest, ManifestError, load_manifest
from .result import Result, load_result

# Repo demos/ directory (sibling of src/).
DEFAULT_DEMOS_DIR = Path(__file__).resolve().parents[3] / "demos"


class Registry:
    def __init__(self, manifests: dict[str, Manifest], demos_dir: Path):
        self.manifests = manifests
        self.demos_dir = demos_dir

    @classmethod
    def load(cls, demos_dir: str | Path | None = None) -> "Registry":
        demos_dir = Path(demos_dir) if demos_dir else DEFAULT_DEMOS_DIR
        manifests: dict[str, Manifest] = {}
        for path in sorted(demos_dir.glob("*.yaml")):
            m = load_manifest(path)
            if m.id in manifests:
                raise ManifestError(f"duplicate demo id {m.id!r} (in {path.name})")
            manifests[m.id] = m
        return cls(manifests, demos_dir)

    def by_domain(self) -> dict[str, list[Manifest]]:
        grouped: dict[str, list[Manifest]] = defaultdict(list)
        for m in self.manifests.values():
            grouped[m.domain].append(m)
        return dict(grouped)

    def demos(self) -> list[Manifest]:
        return [m for m in self.manifests.values() if m.kind == "demo"]

    def recipes(self) -> list[Manifest]:
        return [m for m in self.manifests.values() if m.kind == "recipe"]

    def result_for(self, manifest: Manifest) -> Result | None:
        """Load the result fixture a manifest references, or None."""
        if not manifest.result_ref:
            return None
        path = self.demos_dir / "results" / manifest.result_ref
        if not path.exists():
            return None  # missing fixture -> caller renders as draft (U3)
        return load_result(path)
