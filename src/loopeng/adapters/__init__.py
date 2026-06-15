"""Adapter contracts and (later) bindings to the four external tools (KTD2)."""

from .base import (
    Checkpoint,
    Compounder,
    Factory,
    GenerateResult,
    Judge,
    Refiner,
    Verdict,
)
from .cli_anything import CLIAnythingFactory
from .compound_engineering import ClaudeCodeCompounder, ClaudeCodeRefiner
from .judge import CLIJudge, VarianceReport, parse_report, probe_grade_variance
from .printing_press import PrintingPressFactory

__all__ = [
    "Verdict",
    "GenerateResult",
    "Judge",
    "Refiner",
    "Compounder",
    "Factory",
    "Checkpoint",
    "PrintingPressFactory",
    "CLIAnythingFactory",
    "CLIJudge",
    "parse_report",
    "probe_grade_variance",
    "VarianceReport",
    "ClaudeCodeRefiner",
    "ClaudeCodeCompounder",
]
