"""Autonomous runner + research report (U8). Runner is a deferred unit; the
report renderer works against the memory store today."""

from .report import render_report
from .runner import RunResult, run_loop

__all__ = ["render_report", "run_loop", "RunResult"]
