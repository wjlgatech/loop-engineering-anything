"""The closed loop: controller, convergence policy, brief builder, compound hook (U6)."""

from .controller import LoopController, LoopOutcome, LoopState
from .convergence import Decision, evaluate
from .integrity import (
    IntegrityError,
    assert_heldout_disjoint,
    assert_loop_integrity,
    assert_maker_distinct_from_checker,
    assert_referee_immutable_to_maker,
    confirm_convergence,
    gate_requires_confirmation,
)
from .refactor_brief import build_refactor_brief

__all__ = [
    "LoopController",
    "LoopOutcome",
    "LoopState",
    "Decision",
    "evaluate",
    "build_refactor_brief",
    "IntegrityError",
    "assert_loop_integrity",
    "assert_maker_distinct_from_checker",
    "assert_referee_immutable_to_maker",
    "assert_heldout_disjoint",
    "confirm_convergence",
    "gate_requires_confirmation",
]
