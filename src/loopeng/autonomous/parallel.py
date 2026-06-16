"""Worktree fan-out — run multiple loops concurrently without collisions (U16, R9).

Single responsibility: **concurrency lives here**; cadence stays in
``scheduler/heartbeat.py``. The scheduler decides *which* targets are due and
calls :func:`run_parallel` to drive them; this module decides *how* to run them
side-by-side safely.

Two collision surfaces, two guards:

  - **Filesystem / git.** Each concurrent loop runs in its **own git worktree**
    checked out from the shared repository (``git worktree add``). Worktrees share
    object history but have independent working trees and HEADs, so per-iteration
    ``GitCheckpoint`` snapshots and ``reset --hard`` rollbacks never collide --
    a safety rollback in worktree A cannot disturb worktree B's tree. Each
    worktree is removed (``git worktree remove --force``) on completion, success
    or crash. **``git worktree add``/``remove``/``prune`` are not concurrency-safe**
    against a shared repo -- they race on ``.git/worktrees/`` metadata (a
    ``failed to read .git/worktrees/<x>/commondir`` error). So worktree
    *creation and teardown* are serialized through a lock; the slow part (each
    loop's ``run``) still executes fully in parallel.

  - **Shared SQLite.** Every parallel loop records into one :class:`MemoryStore`.
    That store now serializes all writes through a single shared connection under
    a lock in WAL mode (see ``memory/store.py``), so concurrent ``record_*``
    calls apply one-at-a-time and never corrupt.

Concurrency is **bounded** by ``max_parallel``: excess targets queue and run as
slots free up. A crashed run is **recorded** in its result and **does not** abort
its siblings.
"""

from __future__ import annotations

import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Sequence

# git worktree add/remove/prune mutate shared ``.git/worktrees/`` metadata and are
# NOT safe to run concurrently against one repo; serialize them (the per-target
# loop work still runs in parallel). Module-level so it guards across any
# concurrent ``run_parallel`` calls sharing a repo.
_WORKTREE_LOCK = threading.Lock()

from ..adapters.safety import run_tool


@dataclass(frozen=True)
class ParallelTarget:
    """One unit of fan-out work.

    ``key`` is a stable, filesystem-safe identifier used to name the worktree and
    branch. ``run`` receives the absolute path of the isolated worktree and
    returns an opaque result (typically a run id) that lands in ``ParallelResult``.
    """

    key: str
    run: Callable[[str], object]


@dataclass(frozen=True)
class ParallelResult:
    """Outcome of one fan-out slot. Exactly one of ``value``/``error`` is set."""

    key: str
    worktree: str
    ok: bool
    value: object | None = None
    error: str | None = None


def _safe_key(key: str) -> str:
    import re

    s = re.sub(r"[^A-Za-z0-9._-]+", "-", key).strip("-")
    return s or "target"


def _git_toplevel(repo_dir: str) -> str:
    res = run_tool(["git", "-C", repo_dir, "rev-parse", "--show-toplevel"], timeout=60)
    if not res.ok:
        raise RuntimeError(f"not a git repository: {repo_dir!r} ({res.stderr.strip()})")
    return res.stdout.strip()


def _add_worktree(repo_dir: str, path: str, branch: str) -> None:
    # A fresh branch per worktree keeps the working trees fully independent.
    res = run_tool(
        ["git", "-C", repo_dir, "worktree", "add", "-q", "-B", branch, path, "HEAD"],
        timeout=120,
    )
    if not res.ok:
        raise RuntimeError(f"git worktree add failed for {path!r}: {res.stderr.strip()}")


def _remove_worktree(repo_dir: str, path: str) -> None:
    # --force: the loop will have made commits in the worktree; we want it gone
    # regardless. Best-effort prune + dir removal so a partial add still cleans up.
    run_tool(["git", "-C", repo_dir, "worktree", "remove", "--force", path], timeout=120)
    run_tool(["git", "-C", repo_dir, "worktree", "prune"], timeout=60)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def run_parallel(
    targets: Sequence[ParallelTarget],
    *,
    repo_dir: str,
    worktrees_root: str,
    max_parallel: int = 2,
) -> list[ParallelResult]:
    """Run each target's ``run`` in its own git worktree, at most ``max_parallel``
    at a time, and return one :class:`ParallelResult` per target.

    Worktrees are created under ``worktrees_root`` (created if absent) and removed
    on completion. A target whose ``run`` raises is captured as a failed result
    (``ok=False``, ``error`` set) and never aborts its siblings -- the rest of the
    fan-out completes. Excess targets beyond ``max_parallel`` queue automatically
    via the bounded thread pool.
    """
    if max_parallel < 1:
        raise ValueError("max_parallel must be >= 1")
    if not targets:
        return []

    top = _git_toplevel(repo_dir)
    os.makedirs(worktrees_root, exist_ok=True)

    # Reject duplicate keys early -- two worktrees at the same path would collide.
    seen: set[str] = set()
    plans: list[tuple[ParallelTarget, str, str]] = []
    for t in targets:
        slug = _safe_key(t.key)
        if slug in seen:
            raise ValueError(f"duplicate fan-out key after sanitization: {slug!r}")
        seen.add(slug)
        wt_path = os.path.abspath(os.path.join(worktrees_root, slug))
        branch = f"loopeng/parallel/{slug}"
        plans.append((t, wt_path, branch))

    def _one(target: ParallelTarget, wt_path: str, branch: str) -> ParallelResult:
        try:
            with _WORKTREE_LOCK:  # serialize git worktree metadata mutation (race fix)
                _add_worktree(top, wt_path, branch)
        except Exception as exc:  # worktree could not be created
            return ParallelResult(target.key, wt_path, ok=False, error=str(exc))
        try:
            value = target.run(wt_path)  # the slow part — runs fully in parallel
            return ParallelResult(target.key, wt_path, ok=True, value=value)
        except Exception as exc:  # crashed run: record, clean up, let siblings go
            return ParallelResult(target.key, wt_path, ok=False, error=str(exc))
        finally:
            with _WORKTREE_LOCK:
                _remove_worktree(top, wt_path)

    results: list[ParallelResult] = []
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {pool.submit(_one, t, wt, br): t.key for (t, wt, br) in plans}
        for fut in as_completed(futures):
            results.append(fut.result())

    # Stable order: by the targets' input order, not completion order.
    order = {t.key: i for i, (t, _, _) in enumerate(plans)}
    results.sort(key=lambda r: order[r.key])
    return results
