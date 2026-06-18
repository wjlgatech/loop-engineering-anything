"""Default loop bindings (U1).

Constructs the real ``judge`` / ``refiner`` / ``compounder`` a live loop needs
from config + flags, so the ``run`` CLI (``cli.py``) and the fleet runner
(``orchestration/coordinator.py``) build their dependencies one way instead of
duplicating ``_drive_proof_loop``'s selection logic.

Kept as a leaf module — it imports only the adapters, never ``cli`` or
``orchestration`` — so both layers can depend on it without an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .adapters.base import Compounder, Judge, Refiner
from .adapters.compound_engineering import ClaudeCodeCompounder, ClaudeCodeRefiner
from .adapters.judge import CLIJudge
from .adapters.llm_refiner import PROVIDERS, ChainedRefiner, FallbackLLMRefiner

REFINER_KINDS = ("chain", "claude", "llm")


def _provider_env_keys() -> tuple[str, ...]:
    """Names of the LLM provider API-key env vars the fallback chain *can* use.

    Advisory, not a hard requirement: the chain degrades to a keyless local rung
    (Ollama) when none are set. The CLI surfaces this so an operator is warned
    about silent degradation rather than failing closed on a single key (a hard
    gate would defeat the keyless floor)."""
    return tuple(p.api_key_env for p in PROVIDERS.values() if p.api_key_env)


@dataclass(frozen=True)
class LoopDeps:
    """The concrete tool bindings a loop run needs, ready to pass to
    ``run_refine_loop`` / ``run_loop`` keyword args."""

    judge: Judge
    refiner: Refiner
    compounder: Compounder | None
    # Advisory provider-key names for the chosen refiner (see _provider_env_keys).
    provider_env_keys: tuple[str, ...] = field(default_factory=tuple)


def build_loop_deps(
    *,
    tool_path: str,
    judge_adapter: str,
    refiner_kind: str = "chain",
    compound: bool = True,
) -> LoopDeps:
    """Build the default loop bindings.

    ``refiner_kind``:
      - ``chain``  -> ``ClaudeCodeRefiner`` then ``FallbackLLMRefiner`` (KTD3 default)
      - ``claude`` -> ``ClaudeCodeRefiner`` only
      - ``llm``    -> ``FallbackLLMRefiner`` only (no ``/ce-compound`` step)

    The compounder is ``ClaudeCodeCompounder`` for claude/chain (``None`` when
    ``compound`` is False or for the llm kind — store-only learnings, mirroring
    ``_drive_proof_loop``)."""
    judge = CLIJudge(adapter_path=judge_adapter)

    if refiner_kind == "claude":
        refiner: Refiner = ClaudeCodeRefiner()
        compounder = ClaudeCodeCompounder(tool_path) if compound else None
        provider_keys: tuple[str, ...] = ()
    elif refiner_kind == "llm":
        refiner = FallbackLLMRefiner()
        compounder = None  # store-only learnings; no claude /ce-compound
        provider_keys = _provider_env_keys()
    elif refiner_kind == "chain":
        refiner = ChainedRefiner([ClaudeCodeRefiner(), FallbackLLMRefiner()])
        compounder = ClaudeCodeCompounder(tool_path) if compound else None
        provider_keys = _provider_env_keys()
    else:
        raise ValueError(
            f"unknown refiner_kind {refiner_kind!r}; expected one of: {', '.join(REFINER_KINDS)}"
        )

    return LoopDeps(
        judge=judge, refiner=refiner, compounder=compounder, provider_env_keys=provider_keys
    )
