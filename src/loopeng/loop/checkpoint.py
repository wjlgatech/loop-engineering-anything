"""Checkpoint implementations for regression rollback (U6/U8).

Lives in ``loop/`` (not the autonomous runner) so the controller owns the
mechanism it depends on -- the doc-review flagged the U6->U8 upward dependency
(SG-5). The runner reuses these; it does not define its own.

``GitCheckpoint`` snapshots the generated tool's working tree as a commit and
restores via ``reset --hard``. The tool must live in its own git repo (or a
subdir initialized as one) -- the runner initializes it. ``NoopCheckpoint`` is
for tests and single-pass (no-rollback) runs.

Worktree-aware (U16, R9): ``repo_dir`` may be a *git worktree* checked out from a
shared repository. Because every ``git`` call is scoped to that path with
``git -C``, snapshot/commit/reset operate only on the worktree's own checked-out
branch and working tree. Two parallel loops in two worktrees therefore checkpoint
and roll back independently -- a ``reset --hard`` in worktree A never touches
worktree B's tree (they share object history, not a working tree or HEAD).
"""

from __future__ import annotations

from ..adapters.safety import run_tool


class NoopCheckpoint:
    def snapshot(self) -> str:
        return "noop"

    def restore(self, token: str) -> None:  # pragma: no cover - trivial
        pass


class GitCheckpoint:
    def __init__(self, repo_dir: str):
        self.repo_dir = repo_dir

    def _git(self, *args: str):
        return run_tool(["git", "-C", self.repo_dir, *args], timeout=120)

    def snapshot(self) -> str:
        self._git("add", "-A")
        # Allow empty so a checkpoint is always created even with no changes.
        self._git("commit", "-q", "--allow-empty", "-m", "loop checkpoint")
        head = self._git("rev-parse", "HEAD")
        return head.stdout.strip()

    def restore(self, token: str) -> None:
        self._git("reset", "--hard", token)
