"""SimJudge — the physical-AI-in-sim referee (U12, R4/R5/R6/R12).

Runs a control policy in simulation over a **held-out** seed set and returns a
normalized ``Verdict``: ``score`` is mean reward, ``grade`` is a coarse band of
that score (so the controller's non-null ``grade`` read holds, KTD1), and
``safety_ok`` is the CMDP cost gate (``safety_profile.derive_safety_ok``).

Two integrity properties make this a *referee*, not a self-graded maker:

  * **Held-out seeds are derived at judge-time from a secret PRG seed** that
    lives only inside this object's environment (KTD6/R6) — never written to a
    path the Refiner can read — so the maker cannot overfit to or read the eval
    set. Any seed in ``dev_seeds`` is excluded from the held-out set so the
    final grade is computed on seeds the maker never saw.
  * The simulator is a **gated dependency** (skip-not-fail, KTD9): a missing
    simulator raises ``SimulatorUnavailable`` (a ``RuntimeError``) the e2e gate
    catches, rather than a hard failure in the default suite.

All reporting is bound to **sim performance only** (R12); this module never
emits a transfer / real-world correctness claim.
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ...adapters.base import Verdict
from .safety_profile import PhysicalSafetyProfile


class SimulatorUnavailable(RuntimeError):
    """The simulator (or its GL backend) is absent — the e2e gate skips on this."""


@dataclass(frozen=True)
class Rollout:
    """One simulated episode under a fixed seed (the unit a Simulator returns).

    ``cost`` is the cumulative CMDP cost — a float aggregate or a per-channel
    dict (see ``safety_profile``). ``reward`` may be NaN if the policy errored;
    the judge records that honestly rather than fabricating a score.
    """

    seed: int
    reward: float
    cost: float | dict = 0.0


@runtime_checkable
class Simulator(Protocol):
    """Rolls a policy out under one seed. The real impl wraps MuJoCo Playground;
    tests inject a fake that replays **recorded** rollouts (no live sim)."""

    def rollout(self, policy_path: str, seed: int) -> Rollout: ...


# Coarse reward→letter bands so the controller's non-null ``grade`` read holds
# (KTD1). Ordered high→low by inclusive lower bound. These are *illustrative*
# projections of mean reward, not a physical-correctness scale (R12).
DEFAULT_BANDS: tuple[tuple[float, str], ...] = (
    (0.90, "A"),
    (0.75, "B"),
    (0.50, "C"),
    (0.25, "D"),
    (float("-inf"), "F"),
)


def band_grade(score: float, bands: tuple[tuple[float, str], ...] = DEFAULT_BANDS) -> str:
    """Project a continuous ``score`` onto a coarse letter (KTD1)."""
    if math.isnan(score):
        return "F"
    for lower, letter in bands:
        if score >= lower:
            return letter
    return "F"


def derive_heldout_seeds(secret_seed: int, n: int, *, exclude: frozenset[int]) -> list[int]:
    """Derive ``n`` held-out seeds from a secret PRG seed (KTD6/R6).

    The secret seed lives only in the ``SimJudge`` environment; the derived
    held-out set is never written where the Refiner can read it. Seeds in
    ``exclude`` (the maker's dev seeds) are skipped so the final grade is
    computed on data the maker never trained against.
    """
    if n <= 0:
        raise ValueError("n held-out seeds must be positive")
    rng = random.Random(secret_seed)
    seeds: list[int] = []
    seen: set[int] = set()
    # Bounded draws so a pathological exclude set can't loop forever.
    for _ in range(n * 64):
        if len(seeds) >= n:
            break
        s = rng.randrange(2**31)
        if s in exclude or s in seen:
            continue
        seen.add(s)
        seeds.append(s)
    if len(seeds) < n:
        raise ValueError(f"could not derive {n} held-out seeds disjoint from dev seeds")
    return seeds


@dataclass(frozen=True)
class SimJudge:
    """Referees a policy in sim over a held-out seed set.

    The ``secret_seed`` is the only source of the held-out evaluation seeds and
    must never be persisted alongside the policy. ``n_seeds`` rollouts are
    averaged into ``score`` (mean reward); per-seed variance is reported in
    ``dims`` to feed the controller's ``min_score_gain`` plateau check.
    """

    simulator: Simulator
    secret_seed: int
    n_seeds: int = 8
    safety_profile: PhysicalSafetyProfile = field(default_factory=PhysicalSafetyProfile)
    dev_seeds: frozenset[int] = frozenset()
    bands: tuple[tuple[float, str], ...] = DEFAULT_BANDS

    def heldout_seeds(self) -> list[int]:
        return derive_heldout_seeds(self.secret_seed, self.n_seeds, exclude=self.dev_seeds)

    def judge(self, policy_path: str) -> Verdict:
        """Run the policy over the held-out seeds and normalize to a ``Verdict``.

        Raises ``ValueError`` on an empty rollout set (never a fabricated
        score). A NaN reward on any seed is a *safe failure*: ``safety_ok`` is
        False and the grade is ``F``, recorded honestly rather than passed
        silently. ``safety_ok`` is also False whenever the cumulative CMDP cost
        trips any channel cap.
        """
        seeds = self.heldout_seeds()
        rollouts = [self.simulator.rollout(policy_path, s) for s in seeds]
        if not rollouts:
            raise ValueError("no rollouts produced — cannot grade an empty seed set")

        rewards = [float(r.reward) for r in rollouts]
        had_nan = any(math.isnan(x) for x in rewards)

        # Safety first: any channel trip on any seed fails the gate.
        safety_ok = all(self.safety_profile.safety_ok(r.cost) for r in rollouts)

        if had_nan:
            # Policy errored on at least one seed — record honestly, do not pass.
            failing = [r.seed for r in rollouts if math.isnan(float(r.reward))]
            return Verdict(
                grade="F",
                score=float("nan"),
                dims={"n_seeds": float(len(rollouts)), "nan_rewards": float(len(failing))},
                safety_ok=False,
                failing_fixtures=failing,
            )

        mean_reward = sum(rewards) / len(rewards)
        variance = sum((x - mean_reward) ** 2 for x in rewards) / len(rewards)
        grade = band_grade(mean_reward, self.bands)
        # Below-mean seeds surface as "failing fixtures" so the refiner gets a
        # concrete target, mirroring the software judge's failing-fixture list.
        failing = [r.seed for r, x in zip(rollouts, rewards) if x < mean_reward]
        dims = {
            "mean_reward": mean_reward,
            "reward_variance": variance,
            "n_seeds": float(len(rollouts)),
        }
        return Verdict(
            grade=grade,
            score=mean_reward,
            dims=dims,
            safety_ok=safety_ok,
            failing_fixtures=failing,
        )


def load_simulator() -> Simulator:
    """Construct the real MuJoCo Playground simulator (live runs only, KTD9).

    Gated dependency: imports lazily and raises ``SimulatorUnavailable`` — a
    ``RuntimeError`` the e2e skip guard catches (it covers ``ImportError`` *and*
    ``OSError``/``RuntimeError``, since a missing ``libosmesa`` fails at GL init,
    not import). The default test suite never calls this; it injects a fake
    simulator that replays recorded rollouts.
    """
    os.environ.setdefault("MUJOCO_GL", "osmesa")
    os.environ.setdefault("JAX_DEFAULT_MATMUL_PRECISION", "highest")
    try:  # pragma: no cover - exercised only behind the live e2e gate (U13)
        import mujoco_playground  # type: ignore  # noqa: F401
    except (ImportError, OSError, RuntimeError) as exc:  # pragma: no cover
        raise SimulatorUnavailable(
            "MuJoCo Playground unavailable (install the 'physical-ai' extra and a GL backend)"
        ) from exc
    raise SimulatorUnavailable(  # pragma: no cover - real binding lands in U13
        "live MuJoCo rollout binding is wired in U13; inject a Simulator for tests"
    )
