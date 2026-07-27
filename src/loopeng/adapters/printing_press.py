"""CLI-Printing-Press factory adapter (U4, R1) — service/API lane.

Shell against the documented Printing-Press surface. The exact subcommand/flags
are pinned at build time against the installed version (the adapter boundary
isolates them, KTD2); ``_build_command`` is the single place to adjust them.

This is an adapter SHELL: the command construction, subprocess execution,
timeout/exit-code handling, and output normalization are real and tested with a
mocked ``run_tool``. Binding to a live Printing-Press install is verified once
the tool is present.
"""

from __future__ import annotations

from .base import GenerateResult
from .safety import ProcResult, run_tool, validate_target

# Printing-Press generation is long-running (~30-40 min); give it a wide ceiling.
DEFAULT_TIMEOUT = 60 * 60  # seconds


class PrintingPressFactory:
    def __init__(self, executable: str = "cli-printing-press", timeout: float = DEFAULT_TIMEOUT):
        self.executable = executable
        self.timeout = timeout

    def _build_command(self, target: str, workdir: str) -> list[str]:
        # PINNED SURFACE — verified against cli-printing-press v4.29.0 (2026-07-27):
        # `generate --spec <path|url> --output <dir> --json`. The binary ships as
        # `cli-printing-press`; a HAR target goes through `browser-sniff` first
        # (not yet wired here), and docs URLs use `--docs` via the skill flow.
        return [self.executable, "generate", "--spec", target, "--output", workdir, "--json"]

    def generate(self, target: str, goal: str = "", workdir: str = ".") -> GenerateResult:
        validate_target(target)
        result: ProcResult = run_tool(
            self._build_command(target, workdir), cwd=None, timeout=self.timeout
        )
        return GenerateResult(
            tool_path=workdir,
            lane="service",
            ok=result.ok,
            manifest={"executable": self.executable, "timed_out": result.timed_out},
            logs=(result.stdout + result.stderr)[-4000:],
        )
