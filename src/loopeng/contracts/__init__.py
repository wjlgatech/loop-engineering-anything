"""Declarative, reviewable inputs to the loop (the `loop.yaml` order ticket).

A contract is *parsed and compiled* here into the primitives the engine already
enforces (``config.Budget``, ``config.Lane``, the ``VerificationGate``). It adds
no new controller state and no new runtime behavior: anything a contract cannot
be compiled into is rejected at parse time rather than silently ignored.
"""

from __future__ import annotations

from .run_contract import (  # noqa: F401
    CONTRACT_VERSION,
    EVIDENCE_FIELDS,
    ContractError,
    RunContract,
    describe,
    load_contract,
    missing_evidence,
    parse_contract,
)
