"""Grade-variance probe tests (P0 #2 spike)."""

from __future__ import annotations

import pytest

from loopeng.adapters.base import Verdict
from loopeng.adapters.judge import probe_grade_variance


class CyclingJudge:
    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.i = 0

    def judge(self, tool_path):
        v = self.verdicts[self.i % len(self.verdicts)]
        self.i += 1
        return v


def v(grade, score):
    return Verdict(grade=grade, score=score, dims={}, safety_ok=True)


def test_stable_grades_reported_stable():
    judge = CyclingJudge([v("B", 80), v("B", 80), v("B", 80)])
    report = probe_grade_variance(judge, "tool/", k=3)
    assert report.grade_stable is True
    assert report.score_spread == 0.0


def test_noisy_grades_reported_unstable_with_recommendation():
    judge = CyclingJudge([v("B", 82), v("A", 90), v("B", 78)])
    report = probe_grade_variance(judge, "tool/", k=3)
    assert report.grade_stable is False
    assert report.score_spread == pytest.approx(12.0)
    assert report.recommended_min_score_gain == pytest.approx(12.0)


def test_k_must_be_at_least_two():
    with pytest.raises(ValueError):
        probe_grade_variance(CyclingJudge([v("A", 90)]), "tool/", k=1)
