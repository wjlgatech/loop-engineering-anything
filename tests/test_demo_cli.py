"""U2 demo CLI tests (plan U2 Test scenarios)."""

from __future__ import annotations

import json

import pytest
import yaml
from click.testing import CliRunner

from loopeng.cli import main
from loopeng.demos import registry as registry_mod
from loopeng.memory.store import MemoryStore


def _manifest(**over):
    base = {
        "id": "clinical-trials",
        "title": "ClinicalTrials.gov CLI",
        "domain": "Health",
        "target": "https://clinicaltrials.gov/api/v2",
        "lane": "service",
        "goal": "make trial search agent-native",
        "kind": "demo",
    }
    base.update(over)
    return base


@pytest.fixture
def demos_dir(tmp_path, monkeypatch):
    d = tmp_path / "demos"
    d.mkdir()
    monkeypatch.setattr(registry_mod, "DEFAULT_DEMOS_DIR", d)
    return d


def _write(demos_dir, **over):
    m = _manifest(**over)
    (demos_dir / f"{m['id']}.yaml").write_text(yaml.safe_dump(m))


def test_demo_list_json(demos_dir):
    _write(demos_dir)
    _write(demos_dir, id="legal", domain="Legal", target="https://sec.gov/x")
    result = CliRunner().invoke(main, ["demo", "list", "--json"])
    assert result.exit_code == 0
    rows = json.loads(result.output)
    assert {r["id"] for r in rows} == {"clinical-trials", "legal"}
    assert all("kind" in r and "source" in r for r in rows)


def test_demo_validate_clean_exits_zero(demos_dir):
    _write(demos_dir)
    result = CliRunner().invoke(main, ["demo", "validate"])
    assert result.exit_code == 0
    assert "valid" in result.output


def test_demo_validate_malformed_exits_one(demos_dir):
    (demos_dir / "bad.yaml").write_text(yaml.safe_dump(_manifest(id="bad", target="http://insecure.com")))
    result = CliRunner().invoke(main, ["demo", "validate"])
    assert result.exit_code != 0


def test_demo_show_unknown_errors(demos_dir):
    result = CliRunner().invoke(main, ["demo", "show", "nope"])
    assert result.exit_code != 0
    assert "no demo" in result.output.lower()


def test_demo_run_recipe_refuses(demos_dir):
    _write(demos_dir, id="quant-recipe", kind="recipe")
    result = CliRunner().invoke(main, ["demo", "run", "quant-recipe"])
    assert result.exit_code != 0
    assert "recipe" in result.output.lower()


def test_demo_run_demo_kind_is_gated_stub(demos_dir, monkeypatch):
    _write(demos_dir)
    # Pretend the lane's tools are present so we reach the not-yet-wired gate.
    monkeypatch.setattr("loopeng.preflight.missing_for_lane", lambda lane: [])
    result = CliRunner().invoke(main, ["demo", "run", "clinical-trials"])
    assert result.exit_code != 0
    assert "not yet wired" in result.output.lower()


def test_demo_record_writes_fixture_and_report(demos_dir, tmp_path, monkeypatch):
    _write(demos_dir)
    store = MemoryStore(tmp_path / "rec.db")
    run_id = store.create_run("https://clinicaltrials.gov/api/v2", "service", "g", "2026-06-15T00:00:00Z")
    store.record_iteration(run_id, 1, "C", {}, safety_ok=True)
    store.record_iteration(run_id, 2, "A", {}, safety_ok=True)
    store.finish_run(run_id, "converged", "A")
    monkeypatch.setattr(MemoryStore, "default", classmethod(lambda cls: store))

    result = CliRunner().invoke(main, ["demo", "record", "clinical-trials", "--from", str(run_id)])
    assert result.exit_code == 0, result.output
    fixture = json.loads((demos_dir / "results" / "clinical-trials.json").read_text())
    assert fixture["source"] == "live_verified"
    assert fixture["grade_trajectory"] == ["C", "A"]
    assert fixture["convergence_status"] == "converged"
    assert (demos_dir / "results" / "clinical-trials.report.md").exists()
