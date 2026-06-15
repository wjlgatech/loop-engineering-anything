"""CLI-Anything factory adapter (U4, R1) — codebase lane.

Shell against the documented CLI-Anything surface (7-phase build of a local
dir/repo into a Click CLI + SKILL.md). Exact subcommand/flags pinned at build
time; ``_build_command`` isolates them (KTD2).
"""

from __future__ import annotations

from .base import GenerateResult
from .safety import ProcResult, run_tool, validate_target

DEFAULT_TIMEOUT = 60 * 60  # seconds


class CLIAnythingFactory:
    def __init__(self, executable: str = "cli-anything", timeout: float = DEFAULT_TIMEOUT):
        self.executable = executable
        self.timeout = timeout

    def _build_command(self, target: str, workdir: str) -> list[str]:
        # DOCUMENTED SURFACE — verify against the installed CLI-Anything.
        return [self.executable, "build", target, "--out", workdir]

    def generate(self, target: str, goal: str = "", workdir: str = ".") -> GenerateResult:
        validate_target(target)
        result: ProcResult = run_tool(
            self._build_command(target, workdir), cwd=None, timeout=self.timeout
        )
        return GenerateResult(
            tool_path=workdir,
            lane="codebase",
            ok=result.ok,
            manifest={"executable": self.executable, "timed_out": result.timed_out},
            logs=(result.stdout + result.stderr)[-4000:],
        )
