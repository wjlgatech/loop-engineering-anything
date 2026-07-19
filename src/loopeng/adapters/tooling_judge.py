"""ToolingJudge — the referee for generated agentic tooling (U3, the factory's gap).

The ecosystem-hub factory emits *tooling* (a skill: a ``SKILL.md`` + any bundled
scripts) from a cited repo. Nothing graded that artifact — so a generated skill
could claim capabilities it doesn't ship, reference scripts that don't exist, or
carry an unsafe command, and the loop would have no independent signal. This is
that signal.

It is a **deterministic** ``Judge`` (no LLM): every dimension is a checkable fact
about the artifact on disk, so a grade is cheap, reproducible, and cannot be
gamed by a persuasive description. Three dimensions + a terminal safety gate:

  * **structure** — a loadable ``SKILL.md`` with valid YAML frontmatter carrying a
    non-empty ``name`` and a real ``description``.
  * **fidelity** — the skill does not lie: its ``name`` matches its directory,
    every local file/script it references actually exists, and every referenced
    Python script compiles. This is the "does it do what it claims" check.
  * **safety** — no hard-unsafe command or hardcoded secret in the ``SKILL.md`` or
    any bundled script; a hit sets ``safety_ok=False`` (terminal, KTD5/R3).

``Verdict.score`` is the weighted, measured-dimension sum on 0–100; ``grade`` is a
coarse band of it (so the controller's non-null ``grade`` read holds, KTD1).
"""

from __future__ import annotations

import os
import py_compile
import re
import tempfile
from dataclasses import dataclass

from .base import Verdict

# Coarse score→letter bands (KTD1), high→low by inclusive lower bound.
DEFAULT_BANDS: tuple[tuple[float, str], ...] = (
    (90.0, "A"),
    (75.0, "B"),
    (50.0, "C"),
    (25.0, "D"),
    (float("-inf"), "F"),
)

# Dimension weights (measured dims are renormalized, so an unmeasured dim never
# fake-passes — BRACE: no evidence ⇒ excluded, not a free point).
_WEIGHTS = {"structure": 30.0, "fidelity": 40.0, "safety": 30.0}

# Hard-unsafe patterns → terminal safety failure.
_UNSAFE = (
    (re.compile(r"rm\s+-rf\s+[~/]"), "destructive 'rm -rf' on an absolute/home path"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:"), "fork bomb"),
    (re.compile(r"(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba)?sh"), "pipe-to-shell of a remote script"),
    (re.compile(r"\bsudo\s+rm\b"), "sudo rm"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "hardcoded API key (sk-…)"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "hardcoded AWS access key"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), "hardcoded GitHub token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "embedded private key"),
)

# Tokens in the body that look like references to a shipped local artifact.
_REF = re.compile(r"(?<![\w./-])((?:\./|scripts/|references/|assets/)?[\w./-]+\.(?:py|sh|js|ts|json|yaml|yml))")


def band_grade(score: float, bands: tuple[tuple[float, str], ...] = DEFAULT_BANDS) -> str:
    for lower, letter in bands:
        if score >= lower:
            return letter
    return "F"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Parse leading YAML frontmatter; return (mapping, body). ({}, text) if absent."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    import yaml

    raw = text[3:end]
    body = text[end + 4:]
    try:
        fm = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}, body
    return (fm if isinstance(fm, dict) else {}), body


def _find_skill(tool_path: str) -> str | None:
    if os.path.isfile(tool_path) and os.path.basename(tool_path) == "SKILL.md":
        return tool_path
    cand = os.path.join(tool_path, "SKILL.md")
    return cand if os.path.isfile(cand) else None


def _score_structure(fm: dict) -> tuple[float, list[str]]:
    fixtures: list[str] = []
    checks = 0
    total = 3
    if isinstance(fm, dict) and fm:
        checks += 1
    else:
        fixtures.append("SKILL.md has no valid YAML frontmatter")
    if str(fm.get("name", "")).strip():
        checks += 1
    else:
        fixtures.append("frontmatter missing a non-empty 'name'")
    if len(str(fm.get("description", "")).strip()) >= 20:
        checks += 1
    else:
        fixtures.append("frontmatter 'description' missing or too short (<20 chars)")
    return checks / total, fixtures


def _referenced_files(body: str) -> set[str]:
    out = set()
    for m in _REF.finditer(body):
        tok = m.group(1)
        # Require a path separator: a real bundled-artifact reference carries a dir
        # hint (``scripts/do.py``, ``./run.sh``, ``references/x.md``). A bare
        # ``bun.sh`` / ``config.yaml`` mention is ambiguous (a URL host or a generic
        # noun), so verifying its existence would be a false-positive vaporware flag.
        if "/" in tok:
            out.add(tok.lstrip("./"))
    return out


def _compiles(path: str) -> bool:
    try:
        py_compile.compile(path, doraise=True)
        return True
    except (py_compile.PyCompileError, SyntaxError, OSError):
        return False


def _score_fidelity(fm: dict, body: str, tool_dir: str) -> tuple[float, list[str]]:
    fixtures: list[str] = []
    parts: list[float] = []

    # 1. name matches directory (skills convention).
    name = str(fm.get("name", "")).strip()
    base = os.path.basename(os.path.normpath(tool_dir))
    if name:
        ok = name == base
        parts.append(1.0 if ok else 0.0)
        if not ok:
            fixtures.append(f"frontmatter name {name!r} != directory {base!r}")

    # 2. every referenced local file exists.
    refs = _referenced_files(body)
    if refs:
        present = [r for r in refs if os.path.isfile(os.path.join(tool_dir, r))]
        missing = sorted(set(refs) - set(present))
        parts.append(len(present) / len(refs))
        for r in missing:
            fixtures.append(f"references {r!r} which does not exist (vaporware claim)")
        # 3. referenced python scripts compile.
        pys = [r for r in present if r.endswith(".py")]
        if pys:
            good = [r for r in pys if _compiles(os.path.join(tool_dir, r))]
            parts.append(len(good) / len(pys))
            for r in sorted(set(pys) - set(good)):
                fixtures.append(f"referenced script {r!r} fails to compile")
    else:
        # No concrete artifacts referenced: a pure-instruction skill is allowed,
        # but it earns only partial fidelity (nothing verifiable was claimed).
        parts.append(0.6)
        fixtures.append("no concrete scripts/files referenced — nothing verifiable to ship")

    score = sum(parts) / len(parts) if parts else 0.0
    return score, fixtures


def _score_safety(text: str, tool_dir: str) -> tuple[bool, float, list[str]]:
    corpus = [text]
    for root, _dirs, files in os.walk(tool_dir):
        if "/." in root.replace(tool_dir, "", 1):
            continue
        for fn in files:
            if fn.endswith((".sh", ".py", ".bash", ".zsh")):
                try:
                    corpus.append(open(os.path.join(root, fn), encoding="utf-8", errors="replace").read())
                except OSError:
                    continue
    blob = "\n".join(corpus)
    hits = [why for pat, why in _UNSAFE if pat.search(blob)]
    if hits:
        return False, 0.0, [f"unsafe: {h}" for h in hits]
    return True, 1.0, []


@dataclass
class ToolingJudge:
    """Deterministic ``Judge`` for a skill-shaped tooling artifact."""

    bands: tuple[tuple[float, str], ...] = DEFAULT_BANDS

    def judge(self, tool_path: str) -> Verdict:
        skill = _find_skill(tool_path)
        if skill is None:
            return Verdict("F", 0.0, {"structure": 0.0}, True,
                           ["no SKILL.md found in the tooling artifact"],
                           "not a skill: SKILL.md is absent")
        tool_dir = tool_path if os.path.isdir(tool_path) else os.path.dirname(skill)
        try:
            text = open(skill, encoding="utf-8", errors="replace").read()
        except OSError as e:
            return Verdict("F", 0.0, {"structure": 0.0}, True,
                           [f"cannot read SKILL.md: {e}"], "SKILL.md unreadable")

        fm, body = _split_frontmatter(text)
        struct, sf = _score_structure(fm)
        fide, ff = _score_fidelity(fm, body, tool_dir)
        safe_ok, safe, af = _score_safety(text, tool_dir)

        fracs = {"structure": struct, "fidelity": fide, "safety": safe}
        score = sum(_WEIGHTS[k] * v for k, v in fracs.items()) / sum(_WEIGHTS.values()) * 100.0
        # Two hard gates cap the grade at F regardless of the weighted score:
        #  * safety (KTD5/R3) — a persuasive but unsafe tool never ships;
        #  * loadability — a SKILL.md with no valid frontmatter cannot be loaded or
        #    triggered by any harness, so it is not a usable skill however safe/tidy.
        loadable = bool(fm)
        grade = "F" if (not safe_ok or not loadable) else band_grade(score, self.bands)
        dims = {k: round(v * _WEIGHTS[k], 1) for k, v in fracs.items()}
        fixtures = sf + ff + af
        feedback = (
            f"structure {struct:.0%} · fidelity {fide:.0%} · "
            f"safety {'ok' if safe_ok else 'FAILED'}"
        )
        return Verdict(grade, round(score, 1), dims, safe_ok, fixtures, feedback)


def _self_check() -> None:  # pragma: no cover - manual smoke
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "SKILL.md"), "w").write(
            "---\nname: x\ndescription: a real description of at least twenty chars\n---\nbody\n"
        )
        print(ToolingJudge().judge(d))
