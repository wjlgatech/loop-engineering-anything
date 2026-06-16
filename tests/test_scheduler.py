"""U14 scheduler/heartbeat tests (plan-004 U14 Test scenarios).

The cadence engine fires due targets once per tick, honors the interval, resumes
from the last recorded run, isolates a failing run from its siblings, and no-ops
on an empty schedule — all against an injected fake runner (no live tools, R7).
"""

from __future__ import annotations

import pytest

from loopeng.memory.store import MemoryStore
from loopeng.scheduler import Heartbeat, ScheduledFire


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "sched.db")
    yield s
    s.close()


class RecordingRunner:
    """Returns an incrementing run id and records each fire it received."""

    def __init__(self, *, fail_on=()):
        self.fires: list[ScheduledFire] = []
        self.fail_on = set(fail_on)
        self._next = 100

    def __call__(self, fire: ScheduledFire) -> int:
        self.fires.append(fire)
        if fire.target in self.fail_on:
            raise RuntimeError(f"boom on {fire.target}")
        self._next += 1
        return self._next


def test_tick_fires_due_targets_and_records_run_ids(store):
    runner = RecordingRunner()
    hb = Heartbeat(store, runner)
    hb.schedule("https://a.example.com", interval_seconds=60, goal="improve a")
    hb.schedule("https://b.example.com", interval_seconds=60, goal="improve b")

    fired = hb.tick(now=1000.0)

    assert len(fired) == 2  # both never-fired -> due
    assert {f.target for f in runner.fires} == {"https://a.example.com", "https://b.example.com"}
    # Each run id is persisted as the resume anchor.
    anchors = {e.target: e.last_run_id for e in store.schedules()}
    assert all(v is not None for v in anchors.values())


def test_target_within_interval_is_not_rerun(store):
    runner = RecordingRunner()
    hb = Heartbeat(store, runner)
    hb.schedule("t", interval_seconds=300)

    first = hb.tick(now=1000.0)
    assert len(first) == 1
    # 100s later, still inside the 300s interval -> not due.
    second = hb.tick(now=1100.0)
    assert second == []
    assert len(runner.fires) == 1
    # Past the interval -> fires again.
    third = hb.tick(now=1400.0)
    assert len(third) == 1
    assert len(runner.fires) == 2


def test_wakeup_resumes_from_last_recorded_run(store):
    runner = RecordingRunner()
    hb = Heartbeat(store, runner)
    hb.schedule("t", interval_seconds=60)

    hb.tick(now=1000.0)
    first_run_id = runner.fires[-1]  # actually the returned id; capture from store
    first_anchor = store.schedules()[0].last_run_id

    hb.tick(now=2000.0)  # well past the interval
    second_fire = runner.fires[-1]

    # The second fire carries the first run as its resume anchor, and reuses the
    # same stable workspace -> continues from the checkpoint, not a fresh start.
    assert second_fire.resume_run_id == first_anchor
    assert runner.fires[0].workspace == runner.fires[1].workspace
    assert runner.fires[0].resume_run_id is None  # first run had no prior anchor


def test_failing_run_is_isolated_and_does_not_abort_siblings(store):
    runner = RecordingRunner(fail_on=["bad"])
    hb = Heartbeat(store, runner)
    hb.schedule("bad", interval_seconds=60)
    hb.schedule("good", interval_seconds=60)

    fired = hb.tick(now=1000.0)

    assert len(fired) == 1  # only "good" produced a run id
    by_target = {e.target: e for e in store.schedules()}
    # The failed target's attempt is stamped (won't hot-loop) but keeps no anchor.
    assert by_target["bad"].last_fired == 1000.0
    assert by_target["bad"].last_run_id is None
    # The healthy sibling fired and recorded its run.
    assert by_target["good"].last_run_id is not None


def test_empty_schedule_is_a_noop(store):
    hb = Heartbeat(store, RecordingRunner())
    assert hb.tick(now=1000.0) == []


def test_due_lists_only_due_entries(store):
    hb = Heartbeat(store, RecordingRunner())
    hb.schedule("never", interval_seconds=60)
    hb.tick(now=1000.0)  # marks "never" as fired
    hb.schedule("fresh", interval_seconds=60)  # never fired -> due

    due_targets = {e.target for e in hb.due(now=1010.0)}
    assert due_targets == {"fresh"}  # "never" still inside its interval


def test_non_positive_interval_rejected(store):
    hb = Heartbeat(store, RecordingRunner())
    with pytest.raises(ValueError):
        hb.schedule("t", interval_seconds=0)


def test_reschedule_preserves_resume_anchor(store):
    runner = RecordingRunner()
    hb = Heartbeat(store, runner)
    hb.schedule("t", interval_seconds=60, goal="v1")
    hb.tick(now=1000.0)
    anchor = store.schedules()[0].last_run_id

    # Re-register with a new goal/interval -> cadence updated, anchor preserved.
    hb.schedule("t", interval_seconds=120, goal="v2")
    entry = store.schedules()[0]
    assert entry.goal == "v2"
    assert entry.interval_seconds == 120
    assert entry.last_run_id == anchor


def test_unschedule_removes_target(store):
    hb = Heartbeat(store, RecordingRunner())
    hb.schedule("t", interval_seconds=60)
    assert hb.unschedule("t") is True
    assert store.schedules() == []
    assert hb.unschedule("t") is False  # already gone
