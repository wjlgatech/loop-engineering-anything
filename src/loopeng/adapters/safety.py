"""Subprocess + input-safety helpers shared by the tool adapters.

Encodes the doc-review security findings as reusable primitives:
  - S-3 (command injection): ``run_tool`` always uses an args list with
    ``shell=False``; ``validate_target`` rejects shell metacharacters as
    defense-in-depth before input ever reaches a tool.
  - S-4 (filesystem jail): ``within_workspace`` confirms a path resolves inside
    an allowed root, so applied diffs cannot escape the run's workspace.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

# Classic shell metacharacters and control chars. We run with shell=False so a
# shell never interprets these, but rejecting them early is cheap defense.
_DANGEROUS = re.compile(r"[;|`\n\r\x00]|\$\(")


def validate_target(target: str) -> str:
    """Return ``target`` unchanged, or raise ``ValueError`` if it contains
    shell metacharacters. URL query chars (?, =, &) are allowed."""
    if not target or not str(target).strip():
        raise ValueError("target is empty")
    if _DANGEROUS.search(target):
        raise ValueError(f"target contains disallowed shell metacharacters: {target!r}")
    return target


def within_workspace(path: str, root: str) -> bool:
    """True if ``path`` resolves to ``root`` or a descendant of it."""
    rp = os.path.realpath(path)
    rr = os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


@dataclass(frozen=True)
class ProcResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def run_tool(args: list[str], *, cwd: str | None = None, timeout: float | None = None) -> ProcResult:
    """Run an external tool with ``shell=False``. Never raises for tool failure,
    timeout, or a missing executable -- those are normalized into ``ProcResult``
    so adapters return a structured result instead of leaking a stack trace."""
    try:
        cp = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return ProcResult(cp.returncode, cp.stdout, cp.stderr)
    except subprocess.TimeoutExpired as exc:
        return ProcResult(-1, exc.stdout or "", "timed out", timed_out=True)
    except FileNotFoundError:
        return ProcResult(127, "", f"executable not found: {args[0] if args else '?'}")
