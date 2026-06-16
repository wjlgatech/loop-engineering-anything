"""U12 SimJudge tests — recorded rollouts, CMDP safety, held-out seeds.

No live simulator: a ``RecordedSim`` replays fixtures keyed by seed, exactly the
discipline the plan mandates (live sim runs behind the U13 e2e gate).
"""

from __future__ import annotations

import math

import pytest

from loopeng.domains.physical_ai.safety_profile import (
    DEFAULT_THRESHOLDS,
    PhysicalSafetyProfile,
    derive_safety_ok,
)
from loopeng.domains.physical_ai.sim_judge import (
    Rollout,
    SimJudge,
    band_grade,
    derive_heldout_seeds,
)


class RecordedSim:
    """A fake ``Simulator`` that replays recorded rollouts keyed by seed.

    ``default`` is returned for any seed without an explicit fixture, so a test
    can fix the reward/cost across the whole held-out set without knowing which
    secret seeds get drawn.
    """

    def __init__(self, *, default: tuple[float, float | dict] = (1.0, 0.0), by_seed=None):
        self.default = default
        self.by_seed = by_seed or {}
        self.calls: list[int] = []

    def rollout(self, policy_path: str, seed: int) -> Rollout:
        self.calls.append(seed)
        if seed in self.by_seed:
            reward, cost = self.by_seed[seed]
        else:
            reward, cost = self.default
        return Rollout(seed=seed, reward=reward, cost=cost)


# --- safety_profile: centralized CMDP derivation -----------------------------


def test_cost_over_threshold_trips_regardless_of_reward():
    # R4: a constraint trip makes safety_ok False even with high reward.
    sim = RecordedSim(default=(9.9, {"collision": 1.0}))
    v = SimJudge(simulator=sim, secret_seed=7, n_seeds=4).judge("policy/")
    assert v.safety_ok is False


def test_any_single_channel_trip_fails_closed():
    # Safety derivation is centralized: one bad channel sets safety_ok False.
    ok = {"joint_limit": 0.0, "velocity": 0.5, "torque": 0.5, "collision": 0.0}
    assert derive_safety_ok(ok, DEFAULT_THRESHOLDS) is True
    tripped = {**ok, "torque": 2.0}
    assert derive_safety_ok(tripped, DEFAULT_THRESHOLDS) is False


def test_nan_cost_fails_closed():
    assert derive_safety_ok({"velocity": float("nan")}, DEFAULT_THRESHOLDS) is False
    assert derive_safety_ok(float("nan"), 1.0) is False


def test_float_cost_form():
    assert derive_safety_ok(0.5, 1.0) is True
    assert derive_safety_ok(1.5, 1.0) is False


def test_profile_overrides_default_caps():
    profile = PhysicalSafetyProfile(thresholds={"torque": 5.0})
    assert profile.safety_ok({"torque": 4.0}) is True
    assert profile.safety_ok({"torque": 6.0}) is False


# --- SimJudge: scoring -------------------------------------------------------


def test_mean_reward_maps_to_score_with_variance():
    seeds = derive_heldout_seeds(secret_seed=42, n=2, exclude=frozenset())
    sim = RecordedSim(by_seed={seeds[0]: (1.0, 0.0), seeds[1]: (3.0, 0.0)})
    v = SimJudge(simulator=sim, secret_seed=42, n_seeds=2).judge("policy/")
    assert v.score == pytest.approx(2.0)
    assert v.dims["mean_reward"] == pytest.approx(2.0)
    assert v.dims["reward_variance"] == pytest.approx(1.0)
    assert v.dims["n_seeds"] == 2.0
    assert v.safety_ok is True


def test_grade_is_non_null_band_of_score():
    # KTD1: the controller's non-null grade read must hold.
    assert band_grade(0.95) == "A"
    assert band_grade(0.60) == "C"
    assert band_grade(-5.0) == "F"
    sim = RecordedSim(default=(0.95, 0.0))
    assert SimJudge(simulator=sim, secret_seed=1, n_seeds=3).judge("p/").grade == "A"


# --- SimJudge: held-out seed integrity (R6/KTD6) -----------------------------


def test_heldout_seeds_exclude_dev_seeds():
    # R6: dev seeds the maker trained on are not in the graded set.
    base = derive_heldout_seeds(secret_seed=99, n=5, exclude=frozenset())
    dev = frozenset(base[:2])
    held = derive_heldout_seeds(secret_seed=99, n=5, exclude=dev)
    assert dev.isdisjoint(held)


def test_judge_grades_only_heldout_seeds():
    judge = SimJudge(simulator=RecordedSim(default=(1.0, 0.0)), secret_seed=5, n_seeds=4)
    expected = judge.heldout_seeds()
    sim = RecordedSim(default=(1.0, 0.0))
    SimJudge(simulator=sim, secret_seed=5, n_seeds=4).judge("p/")
    assert sim.calls == expected  # only the secret held-out seeds were rolled out


def test_cannot_derive_when_exclude_exhausts():
    with pytest.raises(ValueError):
        derive_heldout_seeds(secret_seed=3, n=0, exclude=frozenset())


# --- SimJudge: edge cases ----------------------------------------------------


def test_nan_reward_is_safe_failure_not_silent_pass():
    seeds = derive_heldout_seeds(secret_seed=11, n=2, exclude=frozenset())
    sim = RecordedSim(by_seed={seeds[0]: (1.0, 0.0), seeds[1]: (float("nan"), 0.0)})
    v = SimJudge(simulator=sim, secret_seed=11, n_seeds=2).judge("p/")
    assert v.grade == "F"
    assert v.safety_ok is False
    assert math.isnan(v.score)
    assert seeds[1] in v.failing_fixtures


def test_empty_rollout_set_raises_never_fabricates():
    class EmptyJudge(SimJudge):
        def heldout_seeds(self):  # type: ignore[override]
            return []

    judge = EmptyJudge(simulator=RecordedSim(), secret_seed=1, n_seeds=1)
    with pytest.raises(ValueError):
        judge.judge("p/")


def test_determinism_identical_score_across_two_calls():
    # Same policy + same secret seed + same fixtures -> identical score.
    j1 = SimJudge(simulator=RecordedSim(default=(2.5, 0.0)), secret_seed=77, n_seeds=6)
    j2 = SimJudge(simulator=RecordedSim(default=(2.5, 0.0)), secret_seed=77, n_seeds=6)
    assert j1.judge("p/").score == j2.judge("p/").score
    assert j1.heldout_seeds() == j2.heldout_seeds()
