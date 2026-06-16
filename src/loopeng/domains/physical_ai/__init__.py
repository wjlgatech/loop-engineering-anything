"""Physical-AI-in-sim domain (U12/U13, R4/R5/R12).

The third registered ``Domain`` — proof the loop spine is substrate-agnostic.
U12 ships the referee (``SimJudge``) and its CMDP safety profile; U13 adds the
adopt-as-baseline actuator and registers the domain. Everything here is bound to
**sim performance only** (R12): no transfer / real-world correctness claim.
"""

from .safety_profile import (
    COST_CHANNELS,
    DEFAULT_THRESHOLDS,
    PhysicalSafetyProfile,
    derive_safety_ok,
)
from .sim_judge import (
    Rollout,
    Simulator,
    SimJudge,
    SimulatorUnavailable,
    band_grade,
    derive_heldout_seeds,
    load_simulator,
)

__all__ = [
    "COST_CHANNELS",
    "DEFAULT_THRESHOLDS",
    "PhysicalSafetyProfile",
    "derive_safety_ok",
    "Rollout",
    "Simulator",
    "SimJudge",
    "SimulatorUnavailable",
    "band_grade",
    "derive_heldout_seeds",
    "load_simulator",
]
