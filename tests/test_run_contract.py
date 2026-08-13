"""Run-contract tests (plan 2026-08-12 U1).

The contract's whole value is that it is *fail-closed*: it may only declare what
the engine enforces, and it may only tighten the human gate. These pin both, plus
the compile path into ``config.Budget`` and the evidence check against a real
proof pack.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from loopeng.cli import main
from loopeng.config import Budget, Lane
from loopeng.contracts import (
    ContractError,
    RunContract,
    describe,
    load_contract,
    missing_evidence,
    parse_contract,
)

MINIMAL = {"version": 1, "target": "./repo", "goal": "make it agent-native"}


def _write(tmp_path, text: str, name: str = "loop.yaml"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# ----- parsing: the happy path compiles into engine primitives -------------


def test_minimal_contract_compiles_to_engine_defaults():
    c = parse_contract(MINIMAL)
    assert (c.target, c.goal) == ("./repo", "make it agent-native")
    assert c.lane is None  # unset -> the router still classifies
    assert c.budget == Budget()  # no knob is invented by the contract layer
    assert c.evidence_required == ()


def test_budget_block_compiles_every_knob_the_loop_reads():
    c = parse_contract({
        **MINIMAL,
        "budget": {
            "target_grade": "b", "max_iterations": 8, "plateau_patience": 2,
            "plateau_pivots": 0, "token_budget": 250000, "max_wall_seconds": 5400,
            "max_tool_retries": 1, "compression_interval": 3, "min_score_gain": 0.5,
            "target_score": 0.9,
        },
    })
    assert c.budget == Budget(
        target_grade="B", target_score=0.9, max_iterations=8, plateau_patience=2,
        plateau_pivots=0, token_budget=250000, max_wall_seconds=5400.0,
        max_tool_retries=1, compression_interval=3, min_score_gain=0.5,
    )


def test_lane_compiles_to_the_lane_enum():
    assert parse_contract({**MINIMAL, "lane": "service"}).lane is Lane.SERVICE


def test_optional_budget_knobs_accept_explicit_null():
    c = parse_contract({**MINIMAL, "budget": {"token_budget": None, "max_wall_seconds": None}})
    assert c.budget.token_budget is None and c.budget.max_wall_seconds is None


# ----- fail-closed: an unenforced declaration is an ERROR, never a no-op ----


@pytest.mark.parametrize(
    "data",
    [
        {**MINIMAL, "safety": {"forbidden": ["delete_production_data"]}},  # nothing consumes it
        {**MINIMAL, "domain": "software-codebase"},  # the run path cannot force a domain
        {**MINIMAL, "budget": {"max_iteratons": 8}},  # typo
        {**MINIMAL, "evaluation": {"dimensions": ["safety"]}},  # the referee owns its rubric
        {**MINIMAL, "gate": {"require_two_person_review": True}},  # not implemented
    ],
)
def test_unknown_keys_are_rejected_not_silently_ignored(data):
    with pytest.raises(ContractError) as exc:
        parse_contract(data)
    assert "unknown key" in str(exc.value)


def test_error_names_the_offending_section_and_source():
    with pytest.raises(ContractError, match=r"loop\.yaml\.budget:.*max_iteratons"):
        parse_contract({**MINIMAL, "budget": {"max_iteratons": 8}}, source="loop.yaml")


@pytest.mark.parametrize(
    "data,fragment",
    [
        ({"target": "./r", "goal": "g"}, "'version' must be 1"),
        ({"version": 2, "target": "./r", "goal": "g"}, "'version' must be 1"),
        ({"version": 1, "goal": "g"}, "'target' is required"),
        ({"version": 1, "target": "./r"}, "'goal' is required"),
        ({"version": 1, "target": "  ", "goal": "g"}, "non-empty string"),
        ({**MINIMAL, "lane": "cli"}, "'lane' must be one of"),
        ({**MINIMAL, "budget": {"target_grade": "Z"}}, "'target_grade' must be one of"),
        ({**MINIMAL, "budget": {"max_iterations": 0}}, "must be >= 1"),
        ({**MINIMAL, "budget": {"max_iterations": "eight"}}, "must be a number"),
        ({**MINIMAL, "budget": {"max_iterations": True}}, "must be a number"),
        ({**MINIMAL, "budget": {"max_iterations": 2.5}}, "must be a whole number"),
        ({**MINIMAL, "budget": {"max_iterations": None}}, "may not be null"),
        ({**MINIMAL, "evidence": {"required": ["vibes"]}}, "unknown evidence"),
        ({**MINIMAL, "evidence": {"required": "grade_trajectory"}}, "must be a list"),
        ({}, "contract is empty"),
        ([1, 2], "must be a mapping"),
    ],
)
def test_malformed_contracts_are_rejected(data, fragment):
    with pytest.raises(ContractError) as exc:
        parse_contract(data)
    assert fragment in str(exc.value)


# ----- the gate is monotonic: a contract may only tighten ------------------


def test_gate_defaults_to_confirm_required():
    assert parse_contract(MINIMAL).require_human_confirm is True


def test_gate_may_be_restated_true():
    assert parse_contract({**MINIMAL, "gate": {"require_human_confirm": True}}).require_human_confirm


@pytest.mark.parametrize("value", [False, "false", 0, None])
def test_contract_can_never_disable_the_human_gate(value):
    """Anti-surrender: the caller authors the contract, so it must not be able to
    pre-confirm its own run (config.VerificationGate)."""
    with pytest.raises(ContractError, match="may only be true"):
        parse_contract({**MINIMAL, "gate": {"require_human_confirm": value}})


# ----- evidence is a claim checked against a real proof pack ---------------


def test_evidence_names_are_deduped_in_authored_order():
    c = parse_contract({**MINIMAL, "evidence": {"required": ["iterations", "grade_trajectory", "iterations"]}})
    assert c.evidence_required == ("iterations", "grade_trajectory")


def test_missing_evidence_reports_what_the_pack_lacks():
    c = parse_contract({**MINIMAL, "evidence": {"required": ["grade_trajectory", "regression_tests", "token_cost"]}})
    pack = {"before_grade": "F", "after_grade": "A", "iterations": 3, "regression_tests": ["t.py"]}
    assert missing_evidence(c, pack) == ["token_cost"]  # a pack omits, never fakes, a field


def test_no_declared_evidence_is_vacuously_satisfied():
    assert missing_evidence(parse_contract(MINIMAL), {}) == []


# ----- loading from disk ---------------------------------------------------


def test_load_yaml_contract(tmp_path):
    path = _write(tmp_path, """
version: 1
name: qms-agent-native
target: ./qms-kbp
goal: Make the QMS operable by agents.
lane: codebase
budget:
  target_grade: A
  max_iterations: 8
evidence:
  required:
    - grade_trajectory
    - regression_tests
""")
    c = load_contract(path)
    assert c.name == "qms-agent-native" and c.lane is Lane.CODEBASE
    assert c.budget.max_iterations == 8
    assert c.evidence_required == ("grade_trajectory", "regression_tests")
    assert c.source == path  # errors point at the file, not "contract"


def test_load_json_contract(tmp_path):
    path = _write(tmp_path, json.dumps(MINIMAL), name="loop.json")
    assert load_contract(path).target == "./repo"


def test_load_rejects_unsupported_extension(tmp_path):
    with pytest.raises(ContractError, match="must be a .yaml"):
        load_contract(_write(tmp_path, "version: 1", name="loop.txt"))


def test_load_reports_unreadable_file(tmp_path):
    with pytest.raises(ContractError, match="cannot read contract"):
        load_contract(str(tmp_path / "nope.yaml"))


def test_load_reports_malformed_yaml(tmp_path):
    with pytest.raises(ContractError, match="could not parse"):
        load_contract(_write(tmp_path, "version: 1\n  bad: [indent\n"))


def test_describe_is_json_serializable():
    plan = describe(parse_contract({**MINIMAL, "lane": "codebase"}))
    assert json.loads(json.dumps(plan))["lane"] == "codebase"
    assert plan["require_human_confirm"] is True


def test_contract_is_a_frozen_value_object():
    with pytest.raises(Exception):
        RunContract(target="a", goal="b").target = "c"  # type: ignore[misc]


# ----- CLI surface ---------------------------------------------------------


def test_contract_check_prints_the_compiled_plan(tmp_path):
    path = _write(tmp_path, "version: 1\ntarget: ./r\ngoal: g\nbudget:\n  max_iterations: 4\n")
    res = CliRunner().invoke(main, ["contract", "check", path])
    assert res.exit_code == 0, res.output
    assert "budget.max_iterations: 4" in res.output
    assert "require_human_confirm: True" in res.output


def test_contract_check_json_is_machine_readable(tmp_path):
    path = _write(tmp_path, "version: 1\ntarget: ./r\ngoal: g\n")
    res = CliRunner().invoke(main, ["contract", "check", path, "--json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["target"] == "./r"


def test_contract_check_fails_loudly_on_a_bad_contract(tmp_path):
    path = _write(tmp_path, "version: 1\ntarget: ./r\ngoal: g\nsafety:\n  forbidden: [rm]\n")
    res = CliRunner().invoke(main, ["contract", "check", path])
    assert res.exit_code != 0
    assert "unknown key" in res.output


# ----- `run --contract` wiring (plan 2026-08-12 U1) ------------------------
#
# Reuses the `wired` fixture's stubbing idiom from test_run_cli.py so the wiring
# is proven without touching a real factory, judge, or refiner.


@pytest.fixture
def wired(tmp_path, monkeypatch):
    from loopeng.adapters.base import GenerateResult
    from loopeng.autonomous.runner import RunResult
    from loopeng.loop.controller import LoopOutcome, LoopState
    from loopeng.memory.store import MemoryStore

    tool = tmp_path / "ws"
    tool.mkdir()
    adapter = tmp_path / "adapters" / "x.py"
    adapter.parent.mkdir()
    adapter.write_text("x\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    captured: dict = {}

    class FakeFactory:
        def generate(self, target, goal, workdir):
            captured["target"] = target
            captured["gen_goal"] = goal
            return GenerateResult(tool_path=str(tool), lane="codebase", ok=True, manifest={})

    def fake_refine(tool_path, goal, **kw):
        captured["goal"] = goal
        captured.update(kw)
        return RunResult(
            run_id=7,
            outcome=LoopOutcome(LoopState.CONVERGED, "A", "ok", 2, score=0.0, dims={}),
            shippable=True,
        )

    monkeypatch.setattr("loopeng.cli.missing_for_lane", lambda lane: [])
    monkeypatch.setattr(
        "loopeng.autonomous.runner._default_factories",
        lambda: {"cli-anything": FakeFactory(), "printing-press": FakeFactory()},
    )
    monkeypatch.setattr("loopeng.autonomous.runner.run_refine_loop", fake_refine)
    monkeypatch.setattr(MemoryStore, "default", classmethod(lambda cls: MemoryStore(tmp_path / "db.sqlite")))
    return {"repo": repo, "adapter": adapter, "captured": captured}


def test_run_from_contract_drives_the_loop_with_the_compiled_budget(wired, tmp_path):
    path = _write(tmp_path, f"""
version: 1
name: demo
target: {wired["repo"]}
goal: make it agent-native
budget:
  target_grade: B
  max_iterations: 3
""")
    res = CliRunner().invoke(
        main, ["run", "--contract", path, "--judge-adapter", str(wired["adapter"])]
    )
    assert res.exit_code == 0, res.output
    cap = wired["captured"]
    assert cap["goal"] == "make it agent-native"
    assert cap["config"].budget.max_iterations == 3
    assert cap["config"].budget.target_grade == "B"
    assert "Contract: demo" in res.output


def test_run_without_target_or_contract_is_actionable(wired):
    res = CliRunner().invoke(main, ["run"])
    assert res.exit_code != 0
    assert "--contract" in res.output


@pytest.mark.parametrize(
    "extra", [["--goal", "other"], ["--lane", "service"], ["--max-iterations", "9"]]
)
def test_contract_and_conflicting_flag_fail_closed(wired, tmp_path, extra):
    """A flag that also lives in the contract would leave the file no longer
    describing the run it produced -- reject rather than silently pick a winner."""
    path = _write(tmp_path, f"version: 1\ntarget: {wired['repo']}\ngoal: g\n")
    res = CliRunner().invoke(
        main, ["run", "--contract", path, "--judge-adapter", str(wired["adapter"]), *extra]
    )
    assert res.exit_code != 0
    assert "drop the flag" in res.output
    assert "goal" not in wired["captured"]  # the loop never started


def test_positional_target_still_conflicts_with_a_contract(wired, tmp_path):
    path = _write(tmp_path, f"version: 1\ntarget: {wired['repo']}\ngoal: g\n")
    res = CliRunner().invoke(main, ["run", str(wired["repo"]), "--contract", path])
    assert res.exit_code != 0
    assert "TARGET" in res.output


def test_run_reminds_the_operator_to_verify_declared_evidence(wired, tmp_path):
    path = _write(tmp_path, f"""
version: 1
target: {wired["repo"]}
goal: g
evidence:
  required: [grade_trajectory]
""")
    res = CliRunner().invoke(
        main, ["run", "--contract", path, "--judge-adapter", str(wired["adapter"])]
    )
    assert res.exit_code == 0, res.output
    assert "contract evidence" in res.output and "--run 7" in res.output


# ----- `contract evidence` verifies against a real recorded run ------------


@pytest.fixture
def store(tmp_path, monkeypatch):
    from loopeng.memory.store import MemoryStore

    s = MemoryStore(tmp_path / "ev.db")
    monkeypatch.setattr(MemoryStore, "default", classmethod(lambda cls: s))
    yield s
    s.close()


def _record_run(store, *, with_learning: bool):
    run_id = store.create_run("./repo", "codebase", "g", "2026-08-12T10:00:00")
    store.record_iteration(run_id, 1, "F", {"correctness": 10}, True, score=0.1)
    store.record_iteration(run_id, 2, "A", {"correctness": 40}, True, score=0.9)
    if with_learning:
        store.record_learning(run_id, None, "fixed the json contract", "tests/test_x.py")
    store.finish_run(run_id, "converged", "A")
    return run_id


def test_evidence_passes_when_the_pack_carries_every_declared_item(store, tmp_path):
    run_id = _record_run(store, with_learning=True)
    path = _write(tmp_path, """
version: 1
target: ./repo
goal: g
evidence:
  required: [grade_trajectory, dimension_diff, regression_tests]
""")
    res = CliRunner().invoke(main, ["contract", "evidence", path, "--run", str(run_id)])
    assert res.exit_code == 0, res.output
    assert "carries all 3" in res.output


def test_evidence_fails_when_a_declared_item_is_absent(store, tmp_path):
    run_id = _record_run(store, with_learning=False)  # no /ce-compound learning -> no regression tests
    path = _write(tmp_path, """
version: 1
target: ./repo
goal: g
evidence:
  required: [grade_trajectory, regression_tests]
""")
    res = CliRunner().invoke(main, ["contract", "evidence", path, "--run", str(run_id)])
    assert res.exit_code != 0
    assert "MISSING  regression_tests" in res.output
    assert "present  grade_trajectory" in res.output


def test_evidence_on_an_unknown_run_is_actionable(store, tmp_path):
    path = _write(tmp_path, "version: 1\ntarget: ./r\ngoal: g\nevidence:\n  required: [iterations]\n")
    res = CliRunner().invoke(main, ["contract", "evidence", path, "--run", "999"])
    assert res.exit_code != 0
    assert "999" in res.output


def test_evidence_with_nothing_declared_says_so(store, tmp_path):
    path = _write(tmp_path, "version: 1\ntarget: ./r\ngoal: g\n")
    res = CliRunner().invoke(main, ["contract", "evidence", path, "--run", "1"])
    assert res.exit_code == 0, res.output
    assert "declares no evidence" in res.output


def test_shipped_example_contract_stays_valid():
    """The example in docs/ is executable documentation -- it must parse."""
    import pathlib

    path = pathlib.Path(__file__).resolve().parent.parent / "docs" / "examples" / "loop.yaml"
    c = load_contract(str(path))
    assert c.budget.max_iterations == 8
    assert "grade_trajectory" in c.evidence_required
    assert c.require_human_confirm is True
