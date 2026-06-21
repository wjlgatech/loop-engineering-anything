"""U2 memory store tests (plan U2 Test scenarios)."""

from __future__ import annotations

import pytest

from loopeng.memory.fleet_state import FleetItemStatus, FleetRunStatus, FleetTransitionError
from loopeng.memory.store import MemoryStore, grade_rank


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "test.db")
    yield s
    s.close()


def test_record_run_with_iterations_returns_ordered(store):
    run_id = store.create_run("https://api.example.com", "service", "improve it", "2026-06-15T00:00:00Z")
    store.record_iteration(run_id, 1, "C", {"safety": 20}, safety_ok=True)
    store.record_iteration(run_id, 2, "B", {"safety": 20}, safety_ok=True)
    store.record_iteration(run_id, 3, "A", {"safety": 20}, safety_ok=True)
    its = store.iterations(run_id)
    assert [it.n for it in its] == [1, 2, 3]
    assert store.grade_trajectory(run_id) == ["C", "B", "A"]


def test_grade_rank_ordering():
    assert grade_rank("A") > grade_rank("B") > grade_rank("C") > grade_rank("F")
    assert grade_rank("Z") == -1


def test_plateau_true_when_no_gain(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    for n, g in enumerate(["C", "B", "B", "B", "B"], start=1):
        store.record_iteration(run_id, n, g, {}, safety_ok=True)
    # last 3 (B,B,B) do not beat the best-before (max of C,B = B) -> plateau.
    assert store.is_plateaued(run_id, patience=3) is True


def test_plateau_false_when_still_improving(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    for n, g in enumerate(["C", "C", "B", "A"], start=1):
        store.record_iteration(run_id, n, g, {}, safety_ok=True)
    # last 3 (C,B,A) beat best-before (C) -> not plateaued.
    assert store.is_plateaued(run_id, patience=3) is False


def test_plateau_false_when_fewer_than_patience(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    store.record_iteration(run_id, 1, "C", {}, safety_ok=True)
    store.record_iteration(run_id, 2, "C", {}, safety_ok=True)
    assert store.is_plateaued(run_id, patience=3) is False


def test_is_plateaued_since_iteration_gives_postpivot_window_room(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    for n, g in enumerate(["A", "A", "A", "B", "C", "B"], start=1):
        store.record_iteration(run_id, n, g, {}, safety_ok=True)
    # Full trajectory plateaus -- the post-window B/C/B never beat the early A's.
    assert store.is_plateaued(run_id, patience=3) is True
    # Scoped to post-pivot iterations (drop the first 3) -- too few to declare a
    # plateau yet, so the freshly-pivoted strategy gets room to work.
    assert store.is_plateaued(run_id, patience=3, since_iteration=3) is False


def test_recurring_failures_join_across_runs(store):
    r1 = store.create_run("t1", "service", None, "2026-06-15T00:00:00Z")
    r2 = store.create_run("t2", "service", None, "2026-06-15T00:00:00Z")
    store.record_iteration(r1, 1, "C", {}, safety_ok=True, failing_fixtures=["pagination_drift", "token_misclass"])
    store.record_iteration(r2, 1, "C", {}, safety_ok=True, failing_fixtures=["pagination_drift"])
    recurring = store.recurring_failures(min_runs=2)
    assert recurring == [("pagination_drift", 2)]


def test_recurring_failures_target_scoped_excludes_other_targets(store):
    # Same target across two runs -> recurs for that target.
    a1 = store.create_run("target-A", "service", None, "2026-06-15T00:00:00Z")
    a2 = store.create_run("target-A", "service", None, "2026-06-15T00:00:00Z")
    b1 = store.create_run("target-B", "service", None, "2026-06-15T00:00:00Z")
    store.record_iteration(a1, 1, "C", {}, safety_ok=True, failing_fixtures=["fx_a"])
    store.record_iteration(a2, 1, "C", {}, safety_ok=True, failing_fixtures=["fx_a"])
    # target-B fails its own fixture twice -- must NOT leak into target-A's scope.
    store.record_iteration(b1, 1, "C", {}, safety_ok=True, failing_fixtures=["fx_b"])
    store.record_iteration(b1, 2, "C", {}, safety_ok=True, failing_fixtures=["fx_b"])

    scoped = store.recurring_failures(target="target-A")
    assert scoped == [("fx_a", 2)]
    # fx_b recurs only within target-B, never surfaces under target-A.
    assert all(fx != "fx_b" for fx, _ in scoped)


def test_record_and_read_confirmation(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    store.record_confirmation(
        run_id, confirmed=True, reason="converged at grade A; confirm before shipping",
        created="2026-06-16T00:00:00Z",
    )
    rows = store.confirmations(run_id)
    assert len(rows) == 1
    assert rows[0]["confirmed"] is True
    assert "grade A" in rows[0]["reason"]


def test_record_confirmation_rejection(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    store.record_confirmation(run_id, confirmed=False, reason="rejected")
    rows = store.confirmations(run_id)
    assert len(rows) == 1
    assert rows[0]["confirmed"] is False


def test_finish_run_and_list(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    store.finish_run(run_id, "converged", "A")
    run = store.get_run(run_id)
    assert run.status == "converged"
    assert run.final_grade == "A"
    assert store.list_runs()[0].id == run_id


def test_learnings_recorded(store):
    run_id = store.create_run("t", "service", None, "2026-06-15T00:00:00Z")
    it = store.record_iteration(run_id, 1, "B", {}, safety_ok=True)
    store.record_learning(run_id, it, "fixed pagination drift", "tests/test_pagination.py")
    learns = store.learnings(run_id)
    assert len(learns) == 1
    assert learns[0]["summary"] == "fixed pagination drift"


# ----- fleet orchestration (plan-006 U1) -----


def test_fleet_create_items_and_status_roundtrip(store):
    fid = store.create_fleet("improve everything", "2026-06-16T00:00:00Z")
    a = store.add_fleet_item(fid, "a")
    store.add_fleet_item(fid, "b", depends_on=["a"])
    store.set_item_status(a, "running", run_id=101)
    store.set_item_status(a, FleetItemStatus.CONVERGED)
    items = store.fleet_items(fid)
    assert [i.key for i in items] == ["a", "b"]
    assert items[0].status is FleetItemStatus.CONVERGED
    assert items[0].run_id == 101
    assert items[1].depends_on == ["a"]
    assert store.get_fleet(fid).status is FleetRunStatus.RUNNING


def test_fleet_illegal_transition_rejected_by_store(store):
    fid = store.create_fleet(None, "2026-06-16T00:00:00Z")
    a = store.add_fleet_item(fid, "a")
    store.set_item_status(a, "running")
    store.set_item_status(a, "converged")
    with pytest.raises(FleetTransitionError):
        store.set_item_status(a, "running")  # converged -> running is illegal


def test_fleet_outcome_and_escalations(store):
    fid = store.create_fleet(None, "2026-06-16T00:00:00Z")
    a = store.add_fleet_item(fid, "a")
    b = store.add_fleet_item(fid, "b")
    for s in ("running", "blocked", "escalated"):
        store.set_item_status(a, s)
    store.record_item_outcome(a, {"grade": "C", "blocked_reason": "safety"})
    store.set_item_status(b, "running")
    store.set_item_status(b, "converged")
    esc = store.escalations(fid)
    assert [i.key for i in esc] == ["a"]  # only the escalated item
    assert store.fleet_items(fid)[0].outcome["blocked_reason"] == "safety"


def test_fleet_status_set_to_awaiting_human(store):
    fid = store.create_fleet(None, "2026-06-16T00:00:00Z")
    store.set_fleet_status(fid, "awaiting_human", finished="2026-06-16T01:00:00Z")
    f = store.get_fleet(fid)
    assert f.status is FleetRunStatus.AWAITING_HUMAN
    assert f.finished == "2026-06-16T01:00:00Z"


# ----- fork cards (plan 2026-06-17 U5) -----------------------------------


def test_record_and_read_fork_card_round_trips(store):
    run_id = store.create_run("t", "service", None, "2026-06-17T00:00:00Z")
    store.record_fork_card(
        run_id,
        card_id="f1",
        options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        spec_clause="silent",
        chosen_default="a",
        reversibility="reversible",
        blast_radius="local",
        basis="unresolved",
        decision="escalate",
        iteration_id=2,
    )
    cards = store.fork_cards(run_id)
    assert len(cards) == 1
    c = cards[0]
    assert c.card_id == "f1"
    assert c.chosen_default == "a"
    assert c.basis == "unresolved"
    assert c.decision == "escalate"
    assert c.options[0]["id"] == "a"
    assert c.iteration_id == 2


def test_fork_card_nullable_default_and_citation_basis(store):
    run_id = store.create_run("t", "service", None, "2026-06-17T00:00:00Z")
    store.record_fork_card(
        run_id, card_id="f2", chosen_default=None, basis=["kernel.yaml:3"], decision="reverse",
        chosen_option="b",
    )
    c = store.fork_cards(run_id)[0]
    assert c.chosen_default is None
    assert c.basis == ["kernel.yaml:3"]
    assert c.chosen_option == "b"


def test_fork_cards_scoped_and_ordered_per_run(store):
    r1 = store.create_run("t", "service", None, "2026-06-17T00:00:00Z")
    r2 = store.create_run("t", "service", None, "2026-06-17T00:00:00Z")
    store.record_fork_card(r1, card_id="a")
    store.record_fork_card(r1, card_id="b")
    store.record_fork_card(r2, card_id="c")
    assert [c.card_id for c in store.fork_cards(r1)] == ["a", "b"]
    assert [c.card_id for c in store.fork_cards(r2)] == ["c"]


def test_fork_cards_table_present_on_fresh_db_without_migrate(tmp_path):
    s = MemoryStore(tmp_path / "fresh.db")
    try:
        run_id = s.create_run("t", "service", None, "2026-06-17T00:00:00Z")
        s.record_fork_card(run_id, card_id="x")  # would raise if table missing
        assert len(s.fork_cards(run_id)) == 1
    finally:
        s.close()


def test_concurrent_fork_card_writes_do_not_corrupt(store):
    import threading

    run_id = store.create_run("t", "service", None, "2026-06-17T00:00:00Z")

    def writer(i):
        store.record_fork_card(run_id, card_id=f"c{i}")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(store.fork_cards(run_id)) == 20


# ----- learning-reuse flywheel (plan 2026-06-21 U2/U1) --------------------


def _conv_run(store, target, started, *, n_iters, first_grade="C"):
    """Create a converged run with n_iters iterations (first iter grade fixed)."""
    rid = store.create_run(target, "service", "g", started)
    for i in range(1, n_iters + 1):
        g = first_grade if i == 1 else "A"
        store.record_iteration(rid, i, g, {"d": 1}, safety_ok=True)
    store.finish_run(rid, "converged", "A")
    return rid


def test_prior_learnings_scoped_to_target(store):
    a = store.create_run("targetA", "service", "g", "2026-06-20T00:00:00Z")
    b = store.create_run("targetB", "service", "g", "2026-06-20T00:00:00Z")
    store.record_learning(a, None, "A-lesson", grade_delta=2.0)
    store.record_learning(b, None, "B-lesson", grade_delta=2.0)
    # A second run on targetA should retrieve only targetA's prior learning.
    assert store.prior_learnings(target="targetA") == ["A-lesson"]
    assert store.prior_learnings(target="targetB") == ["B-lesson"]


def test_prior_learnings_ranks_by_grade_delta_then_recency(store):
    r = store.create_run("t", "service", "g", "2026-06-20T00:00:00Z")
    store.record_learning(r, None, "small-gain", grade_delta=1.0)
    store.record_learning(r, None, "big-gain", grade_delta=3.0)
    store.record_learning(r, None, "no-delta")  # grade_delta NULL -> ranked last
    got = store.prior_learnings(target="t")
    assert got[0] == "big-gain" and got[1] == "small-gain"
    assert got[-1] == "no-delta"


def test_prior_learnings_limit_caps(store):
    r = store.create_run("t", "service", "g", "2026-06-20T00:00:00Z")
    for i in range(10):
        store.record_learning(r, None, f"lesson-{i}", grade_delta=float(i))
    assert len(store.prior_learnings(target="t", limit=3)) == 3


def test_record_learning_sanitizes_at_write(store):
    r = store.create_run("t", "service", "g", "2026-06-20T00:00:00Z")
    store.record_learning(r, None, "do `rm -rf /`; $(whoami)\x00 and\r\nmore", grade_delta=1.0)
    stored = store.prior_learnings(target="t")[0]
    for bad in ("`", "$", ";", "\x00", "\r", "\n"):
        assert bad not in stored


def test_prior_learnings_empty_on_first_run(store):
    assert store.prior_learnings(target="never-seen") == []


def test_iterations_to_converge_series_oldest_first(store):
    _conv_run(store, "t", "2026-06-18T00:00:00Z", n_iters=4)
    _conv_run(store, "t", "2026-06-19T00:00:00Z", n_iters=2)
    # a non-converged run is excluded
    nr = store.create_run("t", "service", "g", "2026-06-20T00:00:00Z")
    store.record_iteration(nr, 1, "C", {"d": 1}, safety_ok=True)
    store.finish_run(nr, "stopped", "C")
    series = store.iterations_to_converge_series("t")
    assert [n for _, n in series] == [4, 2]  # oldest first, converged only


def test_first_attempt_grade_series(store):
    _conv_run(store, "t", "2026-06-18T00:00:00Z", n_iters=3, first_grade="D")
    _conv_run(store, "t", "2026-06-19T00:00:00Z", n_iters=2, first_grade="B")
    assert [g for _, g in store.first_attempt_grade_series("t")] == ["D", "B"]


def test_compounding_summary_trend(store):
    _conv_run(store, "t", "2026-06-18T00:00:00Z", n_iters=5)
    _conv_run(store, "t", "2026-06-19T00:00:00Z", n_iters=2)
    s = store.compounding_summary("t")
    assert s["converged_runs"] == 2
    assert s["converged_iters_trend"] == "improving"  # 5 -> 2
