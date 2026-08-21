"""Cross-run task success rate (Agent Loop Engineering rubric, section 14).

The rubric asks for tokens, time, iterations AND success rate. The first three are
per-run; this is the only one that needs the whole history. These tests pin the two
choices that decide whether the number is honest:

  * an unfinished run must not move the rate in either direction;
  * a safety block must count as a failure, or the metric rewards the outcome the
    safety gate exists to prevent.
"""

from __future__ import annotations

import pytest

from loopeng.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "sr.db")
    yield s
    s.close()


def _run(store, target: str, status: str | None, grade: str | None = None) -> int:
    run_id = store.create_run(target, "codebase", "g", "2026-08-21T10:00:00")
    if status is not None:
        store.finish_run(run_id, status, grade)
    return run_id


def test_no_finished_runs_reports_none_not_zero(store):
    """0.0 reads as 'we tried and failed'. None reads as 'not measured'."""
    assert store.success_rate()["rate"] is None
    _run(store, "./a", None)  # still running
    out = store.success_rate()
    assert out["rate"] is None and out["running_excluded"] == 1


def test_rate_is_converged_over_finished(store):
    _run(store, "./a", "converged", "A")
    _run(store, "./a", "converged", "A")
    _run(store, "./a", "stopped", "C")
    out = store.success_rate()
    assert out["converged"] == 2 and out["stopped"] == 1
    assert out["finished"] == 3 and out["rate"] == pytest.approx(2 / 3, abs=1e-4)


def test_running_runs_are_excluded_from_the_denominator(store):
    _run(store, "./a", "converged", "A")
    before = store.success_rate()["rate"]
    _run(store, "./a", None)
    after = store.success_rate()
    assert after["rate"] == before == 1.0, "an unfinished run must not move the rate"
    assert after["running_excluded"] == 1


def test_safety_block_counts_as_failure(store):
    """A rate that forgave safety blocks would reward being stopped by the gate."""
    _run(store, "./a", "converged", "A")
    _run(store, "./a", "blocked_safety", None)
    out = store.success_rate()
    assert out["blocked_safety"] == 1
    assert out["rate"] == pytest.approx(0.5), "blocked_safety must sit in the denominator"


def test_target_filter_scopes_the_rate(store):
    _run(store, "./a", "converged", "A")
    _run(store, "./b", "stopped", "D")
    assert store.success_rate("./a")["rate"] == 1.0
    assert store.success_rate("./b")["rate"] == 0.0
    assert store.success_rate()["rate"] == pytest.approx(0.5)


def test_unknown_target_is_unmeasured_not_zero(store):
    _run(store, "./a", "converged", "A")
    out = store.success_rate("./never-run")
    assert out["finished"] == 0 and out["rate"] is None
