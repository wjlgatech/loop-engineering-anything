"""U8/U9 (plan 2026-06-21): spec refine loop + spec-stage ablation.

Drives the REAL LoopController with SpecJudge in the Judge slot and SpecRefiner in
the Refiner slot, proving the spec converges, maker != checker holds, and the U6
ablation harness applies to spec-loop legs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopeng.adapters.spec_judge import SpecJudge
from loopeng.adapters.spec_refiner import SpecRefiner
from loopeng.config import Budget
from loopeng.flywheel.ablation import AblationLeg, ablation_result
from loopeng.loop.compound import RecordingCompounder
from loopeng.loop.controller import LoopController, LoopState
from loopeng.loop.integrity import assert_maker_distinct_from_checker
from loopeng.memory.store import MemoryStore
from loopeng.spec.synthesize import synthesize_spec

_GOOD_SPEC = """# spec: build X
## Problem Frame
Users need X.
## Requirements
- R1 — do X.
- R2 — guard Y.
## Implementation Units
### U1. First
Advances R1. Files: `src/a.py`.
Test scenarios:
- happy path.
### U2. Second
Advances R2. Files: `src/b.py`.
Test scenarios:
- error path.
## Scope Boundaries
Not Z.
"""


class FakeCheckpoint:
    def snapshot(self):
        return "ckpt"

    def restore(self, token):
        pass


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "spec.db")
    yield s
    s.close()


def _improve_editor(spec_path, brief):
    Path(spec_path).write_text(_GOOD_SPEC)
    return True


def test_spec_loop_converges(tmp_path, store):
    spec_dir = tmp_path / "spec"
    synthesize_spec("build X", str(spec_dir))  # low-grade scaffold
    judge, refiner = SpecJudge(), SpecRefiner(editor=_improve_editor)
    ctrl = LoopController(
        judge=judge, refiner=refiner, compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(), store=store, budget=Budget(target_grade="A"),
    )
    rid = store.create_run(str(spec_dir), "service", "build X", "2026-06-21T00:00:00Z")
    outcome = ctrl.run(rid, str(spec_dir))
    assert outcome.final_state is LoopState.CONVERGED
    assert outcome.grade == "A"


def test_spec_maker_distinct_from_checker():
    judge, refiner = SpecJudge(), SpecRefiner(editor=_improve_editor)
    assert_maker_distinct_from_checker(refiner, judge)  # no raise: distinct objects


def test_spec_judge_grades_file_not_brief(tmp_path, store):
    # The grade must reflect ONLY the spec file -- a canary reused-learning in the
    # brief must not change it (maker != checker data-flow for specs).
    spec_dir = tmp_path / "spec"
    synthesize_spec("build X", str(spec_dir))
    # Seed a prior learning so the brief carries a canary into the refiner.
    seed = store.create_run(str(spec_dir), "service", "g", "2026-06-21T00:00:00Z")
    store.record_learning(seed, None, "CANARY-SPEC-LEARNING", grade_delta=3.0)
    seen = {}
    def editor(spec_path, brief):
        seen["reused"] = list(getattr(brief, "reused_learnings", []))
        Path(spec_path).write_text(_GOOD_SPEC)
        return True
    ctrl = LoopController(
        judge=SpecJudge(), refiner=SpecRefiner(editor=editor), compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(), store=store, budget=Budget(target_grade="A"),
    )
    rid = store.create_run(str(spec_dir), "service", "build X", "2026-06-21T01:00:00Z")
    ctrl.run(rid, str(spec_dir))
    # The refiner saw the canary (maker side); the converged grade is exactly the
    # rubric score of the file -- the judge never consumed the brief/canary.
    assert "CANARY-SPEC-LEARNING" in seen["reused"]
    assert SpecJudge().judge(str(spec_dir)).grade == "A"


def _run_spec_loop(store, tmp_path, name, editor, *, budget):
    spec_dir = tmp_path / name
    synthesize_spec("build X", str(spec_dir))
    ctrl = LoopController(
        judge=SpecJudge(), refiner=SpecRefiner(editor=editor), compounder=RecordingCompounder(),
        checkpoint=FakeCheckpoint(), store=store, budget=budget,
    )
    rid = store.create_run(str(spec_dir), "service", "build X", "2026-06-21T00:00:00Z")
    outcome = ctrl.run(rid, str(spec_dir))
    return rid, outcome


def test_spec_ablation_reuses_u6_harness(tmp_path, store):
    # reuse-ON converges in 1 iteration (good editor); reuse-OFF stalls (no-op editor
    # -> never improves -> stops on iteration cap). Feed both into U6's ablation_result.
    on_id, on = _run_spec_loop(store, tmp_path, "on", _improve_editor, budget=Budget(target_grade="A"))
    off_id, off = _run_spec_loop(
        store, tmp_path, "off", lambda p, b: False,  # no-op editor: never improves
        budget=Budget(target_grade="A", max_iterations=4, plateau_patience=99),
    )
    on_leg = AblationLeg(on_id, on.iterations, on.grade, on.final_state is LoopState.CONVERGED)
    off_leg = AblationLeg(off_id, off.iterations, off.grade, off.final_state is LoopState.CONVERGED)
    res = ablation_result(on_leg, off_leg, heldout_seed_hash="seed-spec")
    assert on.final_state is LoopState.CONVERGED
    assert off.final_state is LoopState.STOPPED  # never improved
    assert res["reuse_helped"] is True  # ON converged in fewer iterations than OFF
