"""GitCheckpoint tests against a real temporary git repo (U6/U8 rollback)."""

from __future__ import annotations

import subprocess

import pytest

from loopeng.loop.checkpoint import GitCheckpoint


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "tool.py").write_text("v = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_snapshot_then_restore_reverts_changes(repo):
    cp = GitCheckpoint(str(repo))
    token = cp.snapshot()
    assert token  # a commit SHA

    # Simulate a refactor that regresses the tool.
    (repo / "tool.py").write_text("v = 999  # regression\n")
    cp.restore(token)

    assert (repo / "tool.py").read_text() == "v = 1\n"


def test_snapshot_returns_distinct_shas_across_changes(repo):
    cp = GitCheckpoint(str(repo))
    first = cp.snapshot()
    (repo / "tool.py").write_text("v = 2\n")
    second = cp.snapshot()
    assert first != second
