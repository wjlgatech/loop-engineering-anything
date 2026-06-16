"""U6 convergence-policy tests (pure decision function, R5/KTD6)."""

from __future__ import annotations

from loopeng.adapters.base import Verdict
from loopeng.config import Budget
from loopeng.loop import convergence as cv


def v(grade, safety_ok=True):
    return Verdict(grade=grade, score=0.0, dims={}, safety_ok=safety_ok)


def test_safety_failure_is_blocked_first():
    # Even at target grade, a safety failure wins.
    d = cv.evaluate(v("A", safety_ok=False), Budget(), iterations_done=1, plateaued=False)
    assert d.kind == cv.BLOCKED_SAFETY


def test_target_grade_converges():
    d = cv.evaluate(v("A"), Budget(target_grade="A"), iterations_done=2, plateaued=False)
    assert d.kind == cv.CONVERGED


def test_below_target_with_budget_continues():
    d = cv.evaluate(v("C"), Budget(max_iterations=10), iterations_done=2, plateaued=False)
    assert d.kind == cv.CONTINUE


def test_max_iterations_stops():
    d = cv.evaluate(v("C"), Budget(max_iterations=3), iterations_done=3, plateaued=False)
    assert d.kind == cv.STOPPED
    assert "max iterations" in d.reason


def test_token_budget_stops_when_set():
    d = cv.evaluate(v("C"), Budget(token_budget=1000), iterations_done=2, plateaued=False, tokens_spent=1000)
    assert d.kind == cv.STOPPED
    assert "token" in d.reason


def test_token_budget_ignored_when_none():
    # Default token_budget is None -> token signal never fires.
    d = cv.evaluate(v("C"), Budget(), iterations_done=2, plateaued=False, tokens_spent=10**9)
    assert d.kind == cv.CONTINUE


def test_wall_clock_budget_stops_when_set():
    d = cv.evaluate(
        v("C"), Budget(max_wall_seconds=60.0), iterations_done=2, plateaued=False, elapsed_seconds=60.0
    )
    assert d.kind == cv.STOPPED
    assert "wall-clock" in d.reason


def test_wall_clock_budget_ignored_when_none():
    d = cv.evaluate(v("C"), Budget(), iterations_done=2, plateaued=False, elapsed_seconds=10**6)
    assert d.kind == cv.CONTINUE


def test_wall_clock_stops_even_with_iterations_remaining():
    d = cv.evaluate(
        v("C"),
        Budget(max_iterations=99, max_wall_seconds=30.0),
        iterations_done=2,
        plateaued=False,
        elapsed_seconds=31.0,
    )
    assert d.kind == cv.STOPPED
    assert "wall-clock" in d.reason


def test_plateau_stops():
    d = cv.evaluate(v("C"), Budget(), iterations_done=5, plateaued=True)
    assert d.kind == cv.STOPPED
    assert "plateau" in d.reason


# --- is_improvement (P0 #2 noise-aware acceptance) ---


def s(grade, score):
    return Verdict(grade=grade, score=score, dims={}, safety_ok=True)


def test_better_letter_grade_is_improvement():
    assert cv.is_improvement(s("C", 60), s("B", 61), Budget()) is True


def test_worse_letter_grade_is_not_improvement():
    assert cv.is_improvement(s("B", 99), s("C", 99), Budget()) is False


def test_same_grade_within_noise_band_is_not_improvement():
    # +3 score but a 5-point noise band -> not a real gain.
    assert cv.is_improvement(s("B", 80), s("B", 83), Budget(min_score_gain=5.0)) is False


def test_same_grade_above_noise_band_is_improvement():
    assert cv.is_improvement(s("B", 80), s("B", 86), Budget(min_score_gain=5.0)) is True
