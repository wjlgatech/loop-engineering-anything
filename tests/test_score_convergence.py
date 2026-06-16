"""U10 score-based convergence tests (plan-004 U10 Test scenarios).

A domain can converge on a continuous score target with a measured noise band,
while the letter-grade path stays exactly as before (R2/R3). Safety stays the
first, unbypassable check regardless of score (R6).
"""

from __future__ import annotations

import pytest

from loopeng.adapters.base import Verdict
from loopeng.adapters.judge import probe_grade_variance
from loopeng.config import Budget
from loopeng.loop import convergence as cv
from loopeng.memory.store import MemoryStore


def sv(score, *, grade="C", safety_ok=True):
    """A score-projected verdict (grade is the coarse band, score the signal)."""
    return Verdict(grade=grade, score=score, dims={}, safety_ok=safety_ok)


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "score.db")
    yield s
    s.close()


# ----- evaluate(): score-target convergence ---------------------------------


def test_score_at_or_above_target_converges():
    """Covers R3: target_score=0.9, score 0.91 -> CONVERGED."""
    d = cv.evaluate(sv(0.91), Budget(target_score=0.9), iterations_done=2, plateaued=False)
    assert d.kind == cv.CONVERGED
    assert "0.9" in d.reason


def test_score_below_target_continues():
    d = cv.evaluate(sv(0.89), Budget(target_score=0.9, max_iterations=10), iterations_done=2, plateaued=False)
    assert d.kind == cv.CONTINUE


def test_letter_path_unchanged_when_no_score_target():
    """Regression pin: target_score=None -> letter-grade convergence as before."""
    d = cv.evaluate(sv(0.0, grade="A"), Budget(target_grade="A"), iterations_done=2, plateaued=False)
    assert d.kind == cv.CONVERGED


def test_score_target_skips_letter_ladder():
    """A high letter grade does NOT converge a score-target run below its score."""
    d = cv.evaluate(
        sv(0.5, grade="A"), Budget(target_score=0.9, max_iterations=10), iterations_done=1, plateaued=False
    )
    assert d.kind == cv.CONTINUE  # grade A is ignored; score 0.5 < 0.9


def test_safety_first_even_above_score_target():
    """Structural: safety_ok=False -> BLOCKED_SAFETY even when score >> target."""
    d = cv.evaluate(sv(0.99, safety_ok=False), Budget(target_score=0.9), iterations_done=1, plateaued=False)
    assert d.kind == cv.BLOCKED_SAFETY


def test_budget_stops_still_fire_under_score_target():
    big = Budget(target_score=0.99, max_iterations=3, token_budget=1000)
    assert cv.evaluate(sv(0.5), big, iterations_done=3, plateaued=False).kind == cv.STOPPED
    assert cv.evaluate(sv(0.5), big, iterations_done=1, plateaued=False, tokens_spent=1000).kind == cv.STOPPED
    assert cv.evaluate(sv(0.5), big, iterations_done=1, plateaued=True).kind == cv.STOPPED


# ----- is_improvement(): score delta inside a letter band -------------------


def test_within_letter_score_gain_accepted_under_score_target():
    b = Budget(target_score=0.9, min_score_gain=0.01)
    assert cv.is_improvement(sv(0.70, grade="C"), sv(0.80, grade="C"), b) is True


def test_within_letter_score_regression_rolled_back_under_score_target():
    b = Budget(target_score=0.9, min_score_gain=0.01)
    assert cv.is_improvement(sv(0.80, grade="C"), sv(0.70, grade="C"), b) is False


def test_score_delta_below_noise_band_is_not_improvement():
    b = Budget(target_score=0.9, min_score_gain=0.05)
    assert cv.is_improvement(sv(0.80), sv(0.83), b) is False  # +0.03 < 0.05 band


# ----- plateau on score ------------------------------------------------------


def test_plateau_fires_on_flat_score_trajectory(store):
    run_id = store.create_run("policy/", "physical-ai-sim", None, "2026-06-15T00:00:00Z")
    # Score rises then flattens; grade is a constant band the whole time.
    for n, score in enumerate([0.40, 0.55, 0.55, 0.55, 0.55], start=1):
        store.record_iteration(run_id, n, "C", {}, safety_ok=True, score=score)
    # Letter-only plateau would see constant "C" and misfire; score plateau is
    # the correct signal -- last 3 (0.55) do not beat best-before (0.55).
    assert store.is_plateaued(run_id, patience=3, on_score=True) is True


def test_no_plateau_while_score_still_rising(store):
    run_id = store.create_run("policy/", "physical-ai-sim", None, "2026-06-15T00:00:00Z")
    for n, score in enumerate([0.40, 0.50, 0.60, 0.70], start=1):
        store.record_iteration(run_id, n, "C", {}, safety_ok=True, score=score)
    assert store.is_plateaued(run_id, patience=3, on_score=True) is False


def test_plateau_falls_back_to_grades_when_scores_missing(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    for n, g in enumerate(["C", "B", "B", "B", "B"], start=1):
        store.record_iteration(run_id, n, g, {}, safety_ok=True)  # no score
    # on_score requested but no scores recorded -> grade ladder, still plateaus.
    assert store.is_plateaued(run_id, patience=3, on_score=True) is True


# ----- variance probe sets the score band -----------------------------------


def test_variance_probe_raises_band_for_noisy_referee():
    """A stochastic referee's spread feeds a non-zero min_score_gain (R6)."""

    class StochasticJudge:
        def __init__(self, scores):
            self.scores = scores
            self.i = 0

        def judge(self, tool_path):
            s = self.scores[self.i % len(self.scores)]
            self.i += 1
            return Verdict(grade="C", score=s, dims={}, safety_ok=True)

    noisy = probe_grade_variance(StochasticJudge([0.60, 0.72, 0.55]), "policy/", k=3)
    stable = probe_grade_variance(StochasticJudge([0.60, 0.60, 0.60]), "policy/", k=3)
    assert noisy.recommended_min_score_gain > stable.recommended_min_score_gain
    assert stable.recommended_min_score_gain == 0.0


# ----- end-to-end: controller drives a score-target loop --------------------


def test_controller_converges_on_score_target(store):
    """The loop accepts within-band score gains and converges on the score
    target while every iteration's grade stays a constant projected band."""
    from loopeng.loop.compound import RecordingCompounder
    from loopeng.loop.controller import LoopController, LoopState

    class ScriptedJudge:
        def __init__(self, verdicts):
            self.verdicts = verdicts
            self.calls = 0

        def judge(self, tool_path):
            v = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
            self.calls += 1
            return v

    class FakeRefiner:
        def refactor(self, tool_path, brief):
            return "diff"

    class FakeCheckpoint:
        def snapshot(self):
            return "ckpt"

        def restore(self, token):
            pass

    judge = ScriptedJudge([sv(0.40), sv(0.65), sv(0.92)])  # all grade "C", rising score
    ctrl = LoopController(
        judge=judge,
        refiner=FakeRefiner(),
        compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(),
        store=store,
        budget=Budget(target_score=0.9, min_score_gain=0.01, max_iterations=10),
    )
    run_id = store.create_run("policy/", "physical-ai-sim", "improve", "2026-06-15T00:00:00Z")

    outcome = ctrl.run(run_id, "policy/")

    assert outcome.final_state is LoopState.CONVERGED
    assert [it.score for it in store.iterations(run_id)] == pytest.approx([0.40, 0.65, 0.92])
