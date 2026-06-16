"""U17: maker/checker contract + anti-cognitive-surrender gate tests (R6/R10)."""

from __future__ import annotations

import pytest

from loopeng.adapters.base import GenerateResult, Verdict
from loopeng.autonomous.runner import run_loop
from loopeng.config import Budget, Config, VerificationGate
from loopeng.loop.checkpoint import NoopCheckpoint
from loopeng.loop.compound import RecordingCompounder
from loopeng.loop.controller import LoopState
from loopeng.loop.integrity import (
    IntegrityError,
    assert_heldout_disjoint,
    assert_loop_integrity,
    assert_maker_distinct_from_checker,
    assert_referee_immutable_to_maker,
    confirm_convergence,
    gate_requires_confirmation,
)
from loopeng.memory.store import MemoryStore


def v(grade, safety_ok=True):
    return Verdict(grade=grade, score=0.0, dims={"correctness": 30}, safety_ok=safety_ok)


class ScriptedJudge:
    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = 0

    def judge(self, tool_path):
        verdict = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return verdict


class FakeRefiner:
    def refactor(self, tool_path, brief):
        return "diff"


class FakeFactory:
    def __init__(self, ok=True, lane="service"):
        self.ok = ok
        self.lane = lane

    def generate(self, target, goal="", workdir="."):
        return GenerateResult(tool_path=workdir, lane=self.lane, ok=self.ok)


class MakerCheckerSameObject:
    """A single object playing both roles — the wiring U17 must reject."""

    def refactor(self, tool_path, brief):
        return "diff"

    def judge(self, tool_path):
        return v("A")


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "mc.db")
    yield s
    s.close()


# ----- maker ≠ checker contract (R10) ------------------------------------


def test_maker_equals_checker_rejected():
    agent = MakerCheckerSameObject()
    with pytest.raises(IntegrityError, match="same object"):
        assert_maker_distinct_from_checker(agent, agent)


def test_distinct_maker_checker_passes():
    assert_maker_distinct_from_checker(FakeRefiner(), ScriptedJudge([v("A")]))


def test_missing_role_rejected():
    with pytest.raises(IntegrityError, match="both be wired"):
        assert_maker_distinct_from_checker(None, ScriptedJudge([v("A")]))


def test_run_loop_rejects_same_maker_checker_before_any_work(store, tmp_path):
    """The assertion fires before preflight/factory — no work starts."""
    agent = MakerCheckerSameObject()
    with pytest.raises(IntegrityError, match="same object"):
        run_loop(
            "https://api.example.com",
            "improve it",
            judge=agent,
            refiner=agent,
            compounder=RecordingCompounder(),
            store=store,
            workspace_root=str(tmp_path / "ws"),
            factories={"printing-press": FakeFactory()},
            checkpoint=NoopCheckpoint(),
            check_missing=lambda lane: [],
        )
    # No run row was created — failed closed before create_run.
    assert store.list_runs() == []


# ----- held-out seed disjointness (R6/KTD6) ------------------------------


def test_heldout_overlap_rejected():
    with pytest.raises(IntegrityError, match="overlap"):
        assert_heldout_disjoint(dev_seeds=[1, 2, 3], heldout_seeds=[3, 4, 5])


def test_heldout_disjoint_passes():
    assert_heldout_disjoint(dev_seeds=[1, 2, 3], heldout_seeds=[4, 5, 6])


def test_empty_heldout_rejected():
    with pytest.raises(IntegrityError, match="empty"):
        assert_heldout_disjoint(dev_seeds=[1, 2], heldout_seeds=[])


def test_half_declared_seeds_rejected():
    with pytest.raises(IntegrityError, match="must declare both"):
        assert_loop_integrity(
            refiner=FakeRefiner(),
            judge=ScriptedJudge([v("A")]),
            dev_seeds=[1, 2, 3],
            heldout_seeds=None,
        )


# ----- referee immutability (R6/KTD6) ------------------------------------


def test_referee_inside_maker_write_surface_rejected(tmp_path):
    """Model immutability at the contract level: a refine path that can write
    the referee definition is rejected."""
    policy_dir = tmp_path / "policy"  # the maker's write surface
    referee = tmp_path / "policy" / "sim_judge.py"  # referee living INSIDE it
    with pytest.raises(IntegrityError, match="referee-immutability"):
        assert_referee_immutable_to_maker(
            referee_paths=[str(referee)], maker_write_paths=[str(policy_dir)]
        )


def test_referee_outside_maker_write_surface_passes(tmp_path):
    policy_dir = tmp_path / "policy"
    referee = tmp_path / "referee" / "sim_judge.py"  # disjoint subtree
    assert_referee_immutable_to_maker(
        referee_paths=[str(referee)], maker_write_paths=[str(policy_dir)]
    )


# ----- human-confirm gate / anti-cognitive-surrender (R10) ---------------


def _gate(**kw):
    return VerificationGate(**kw)


def test_gate_blocks_converged_until_confirmed():
    gate = _gate()  # ON by default
    # Attended, no CI, not confirmed -> not shippable yet.
    assert confirm_convergence(gate, scheduled=False, confirmed=False, env={}) is False
    # Human confirms -> shippable.
    assert confirm_convergence(gate, scheduled=False, confirmed=True, env={}) is True


def test_ci_mode_bypasses_attended_gate():
    gate = _gate()
    assert gate_requires_confirmation(gate, scheduled=False, env={"CI": "true"}) is False
    assert confirm_convergence(gate, scheduled=False, confirmed=False, env={"CI": "true"}) is True


def test_scheduled_run_requires_confirm_even_with_ci_flag():
    """Anti-surrender default: a scheduler setting CI=true cannot auto-ship."""
    gate = _gate()
    assert gate_requires_confirmation(gate, scheduled=True, env={"CI": "true"}) is True
    assert confirm_convergence(gate, scheduled=True, confirmed=False, env={"CI": "true"}) is False
    # Only an explicit human confirm ships a scheduled run.
    assert confirm_convergence(gate, scheduled=True, confirmed=True, env={"CI": "true"}) is True


def test_gate_off_never_requires_confirm():
    gate = _gate(require_human_confirm=False)
    assert gate_requires_confirmation(gate, scheduled=True, env={"CI": "true"}) is False
    assert confirm_convergence(gate, scheduled=True, confirmed=False, env={}) is True


def test_gate_default_is_confirm_required():
    """Edge: out-of-the-box config is confirm-required (anti-surrender default)."""
    cfg = Config()
    assert cfg.gate.require_human_confirm is True
    assert gate_requires_confirmation(cfg.gate, scheduled=True, env={}) is True


# ----- gate wired through the runner -------------------------------------


def _run_to_convergence(store, tmp_path, *, scheduled, confirmed, env_ci=None, gate=None):
    cfg = Config(gate=gate or VerificationGate())
    if env_ci is not None:
        import os

        os.environ["CI"] = env_ci
    try:
        return run_loop(
            "https://api.example.com",
            "improve it",
            judge=ScriptedJudge([v("C"), v("B"), v("A")]),
            refiner=FakeRefiner(),
            compounder=RecordingCompounder(),
            store=store,
            config=cfg,
            budget=Budget(target_grade="A"),
            workspace_root=str(tmp_path / "ws"),
            factories={"printing-press": FakeFactory()},
            checkpoint=NoopCheckpoint(),
            check_missing=lambda lane: [],
            scheduled=scheduled,
            confirmed=confirmed,
        )
    finally:
        if env_ci is not None:
            import os

            os.environ.pop("CI", None)


def test_runner_converged_not_shippable_until_confirmed(store, tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    result = _run_to_convergence(store, tmp_path, scheduled=False, confirmed=False)
    assert result.outcome.final_state is LoopState.CONVERGED
    assert result.shippable is False  # 'done' is a claim until confirmed
    result2 = _run_to_convergence(store, tmp_path, scheduled=False, confirmed=True)
    assert result2.shippable is True


def test_runner_ci_bypass_marks_shippable(store, tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "true")
    result = _run_to_convergence(store, tmp_path, scheduled=False, confirmed=False)
    assert result.outcome.final_state is LoopState.CONVERGED
    assert result.shippable is True


def test_runner_scheduled_ignores_ci_flag(store, tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "true")
    result = _run_to_convergence(store, tmp_path, scheduled=True, confirmed=False)
    assert result.shippable is False  # scheduler cannot auto-ship via CI


def test_runner_non_converged_never_shippable(store, tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "true")
    result = run_loop(
        "https://api.example.com",
        "improve it",
        judge=ScriptedJudge([v("C", safety_ok=False)]),
        refiner=FakeRefiner(),
        compounder=RecordingCompounder(),
        store=store,
        config=Config(),
        budget=Budget(target_grade="A"),
        workspace_root=str(tmp_path / "ws"),
        factories={"printing-press": FakeFactory()},
        checkpoint=NoopCheckpoint(),
        check_missing=lambda lane: [],
        confirmed=True,
    )
    assert result.outcome.final_state is LoopState.BLOCKED_SAFETY
    assert result.shippable is False


# ----- U5: legible gate + recorded verdict (R10, KTD5) -------------------


def test_describe_gate_reason_names_lowest_dimension():
    from loopeng.loop.integrity import describe_gate_reason

    reason = describe_gate_reason("A", 87.0, {"correctness": 90, "safety": 70})
    assert "grade A" in reason
    assert "safety" in reason  # the borderline (lowest) dimension
    assert "confirm" in reason.lower()


def test_runner_records_human_approval_and_surfaces_reason(store, tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    result = _run_to_convergence(store, tmp_path, scheduled=False, confirmed=True)
    assert result.shippable is True
    assert result.gate_reason is not None and "grade A" in result.gate_reason
    rows = store.confirmations(result.run_id)
    assert len(rows) == 1
    assert rows[0]["confirmed"] is True
    assert rows[0]["reason"] == result.gate_reason


def test_runner_records_rejection_and_stays_unshippable(store, tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    result = _run_to_convergence(store, tmp_path, scheduled=False, confirmed=False)
    assert result.shippable is False
    rows = store.confirmations(result.run_id)
    assert len(rows) == 1
    assert rows[0]["confirmed"] is False  # the rejection is persisted for audit


def test_ci_bypass_records_nothing_but_ships(store, tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "true")
    result = _run_to_convergence(store, tmp_path, scheduled=False, confirmed=False)
    assert result.shippable is True
    assert result.gate_reason is None  # no confirmation owed -> nothing surfaced
    assert store.confirmations(result.run_id) == []  # observational: no owed, no record


def test_recording_is_write_only_does_not_affect_shippability(store, tmp_path, monkeypatch):
    # A persisted approval from a prior run never makes a later rejection ship.
    monkeypatch.delenv("CI", raising=False)
    approved = _run_to_convergence(store, tmp_path, scheduled=False, confirmed=True)
    assert approved.shippable is True
    rejected = _run_to_convergence(store, tmp_path, scheduled=False, confirmed=False)
    assert rejected.shippable is False  # confirm_convergence is the sole authority
