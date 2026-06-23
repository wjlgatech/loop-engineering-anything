"""Architectural fitness functions (plan 2026-06-22 U1).

These tests mechanize design invariants that are ALREADY TRUE in the codebase, so
they pass on arrival and fail the moment a change erodes the architecture:

  - no concrete-class inheritance (composition over inheritance)
  - value-object dataclasses are frozen
  - the pure core imports no effects (DIRECT imports only -- see KTD7)
  - the controller depends only on `adapters.base` protocols
  - the maker != checker integrity assertions stay wired at runner entry

Scope honesty (KTD7): these are stdlib-`ast` string/structure checks -- honest-code
drift-detectors, NOT adversary-proof. Aliased / dynamic / re-exported imports can
evade them; alias-proof enforcement is the deferred `import-linter` option. They
deliberately do NOT forbid `getattr` (the KTD1 protocol-bound-read convention).
"""

from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "loopeng"

# Bases a class may inherit from without it counting as "concrete inheritance".
_ALLOWED_BASES = {"Protocol", "Enum", "IntEnum", "str", "ABC", "object"}
# Effect modules the pure core must not DIRECTLY import.
_FORBIDDEN_CORE_IMPORTS = {
    "os", "sys", "sqlite3", "subprocess", "socket", "urllib", "http", "requests", "click",
}
# The pure-core modules (relative to SRC). loop/grades.py joins this set in U2.
_PURE_CORE = [
    "grades.py",
    "loop/convergence.py",
    "loop/refactor_brief.py",
    "spec/rubric.py",
    "flywheel/oracle.py",
]


def _py_files():
    return [p for p in SRC.rglob("*.py")]


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):  # e.g. Protocol[...] / Generic[T]
        return _base_name(node.value)
    return None


def _is_allowed_base(name: str | None) -> bool:
    if name is None:
        return True  # unrecognized expression base -> don't false-positive
    return name in _ALLOWED_BASES or name.endswith(("Error", "Exception"))


def _direct_imports(tree: ast.AST) -> set[str]:
    """Top-level names of DIRECT imports in a module (not transitive)."""
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module.split(".")[0])
    return out


def _adapters_imports(tree: ast.AST) -> set[str]:
    """The `adapters.<X>` submodules a module imports (X after 'adapters.')."""
    found: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and "adapters" in n.module:
            mod = n.module.lstrip(".")
            if ".adapters." in f".{mod}." or mod.startswith("adapters."):
                tail = mod.split("adapters.", 1)[1]
                found.add(tail.split(".")[0])
    return found


# ----- (a) no concrete inheritance ----------------------------------------


def test_no_concrete_class_inheritance():
    offenders = []
    for p in _py_files():
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if not _is_allowed_base(_base_name(base)):
                        offenders.append(f"{p.relative_to(SRC)}:{node.name} -> {_base_name(base)}")
    assert not offenders, f"concrete-class inheritance found (use composition/protocols): {offenders}"


def test_no_inheritance_checker_detects_violation():
    tree = ast.parse("class Base:\n    pass\nclass Child(Base):\n    pass\n")
    bad = [
        _base_name(b)
        for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        for b in node.bases if not _is_allowed_base(_base_name(b))
    ]
    assert bad == ["Base"]  # the checker bites


# ----- (b) value-object dataclasses are frozen ----------------------------


def _frozen_offenders(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text())
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                if _base_name(target) == "dataclass":
                    frozen = isinstance(dec, ast.Call) and any(
                        kw.arg == "frozen" and getattr(kw.value, "value", False) is True
                        for kw in dec.keywords
                    )
                    if not frozen:
                        bad.append(node.name)
    return bad


def test_base_contracts_are_frozen_value_objects():
    # adapters/base.py is the value-object module: every dataclass there is frozen.
    bad = _frozen_offenders(SRC / "adapters" / "base.py")
    assert not bad, f"non-frozen value-object dataclasses in adapters/base.py: {bad}"


def test_frozen_checker_detects_mutable_dataclass():
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write("from dataclasses import dataclass\n@dataclass\nclass X:\n    a: int = 0\n")
        name = fh.name
    assert _frozen_offenders(pathlib.Path(name)) == ["X"]


# ----- (c) pure core imports no effects (direct imports only) -------------


def test_pure_core_has_no_direct_effect_imports():
    offenders = {}
    for rel in _PURE_CORE:
        p = SRC / rel
        if not p.exists():
            continue
        hit = _direct_imports(ast.parse(p.read_text())) & _FORBIDDEN_CORE_IMPORTS
        if hit:
            offenders[rel] = sorted(hit)
    assert not offenders, f"pure-core modules directly import effects: {offenders}"


def test_purity_checker_detects_effect_import():
    tree = ast.parse("import os\nfrom x import y\n")
    assert _direct_imports(tree) & _FORBIDDEN_CORE_IMPORTS == {"os"}


# ----- (d) controller depends only on adapters.base -----------------------


def test_controller_imports_only_adapters_base():
    tree = ast.parse((SRC / "loop" / "controller.py").read_text())
    non_base = _adapters_imports(tree) - {"base"}
    assert not non_base, f"controller imports concrete adapters (only adapters.base allowed): {non_base}"


def test_controller_deps_checker_detects_concrete_adapter():
    tree = ast.parse("from ..adapters.judge import CLIJudge\n")
    assert _adapters_imports(tree) == {"judge"}


# ----- (e) maker != checker integrity stays wired -------------------------


def test_integrity_assertion_wired_at_runner_entry():
    runner = (SRC / "autonomous" / "runner.py").read_text()
    # Both entrypoints (run_loop + run_refine_loop) assert loop integrity before work.
    assert runner.count("assert_loop_integrity(") >= 2, "integrity must be asserted at both runner entrypoints"
    integrity = (SRC / "loop" / "integrity.py").read_text()
    assert "is judge" in integrity, "maker != checker identity check (refiner is judge) must remain"
