"""Heartbeat — durable cadence over registered targets (U14, R7).

The engine is deliberately runner-agnostic: it owns *when* to fire (cadence,
due-calculation, failure isolation, durable state) and delegates *how* to fire
to an injected ``runner`` callable, exactly as the controller delegates
generation/judging to injected protocols. This keeps it testable without live
tools and lets the same engine drive any wired runner (refine loop, full
generate loop, or a platform-cron shim later).

Durable by design: schedule state lives in SQLite, so a process restart resumes
the cadence from the last recorded run rather than from scratch.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Callable

from ..memory.store import MemoryStore, ScheduleEntry


@dataclass(frozen=True)
class ScheduledFire:
    """Context handed to the runner for one due target.

    ``resume_run_id`` is the last successful run for this target and
    ``workspace`` is stable across ticks, so the runner continues from the
    recorded checkpoint instead of a fresh baseline (R7 resume).
    """

    target: str
    goal: str
    domain: str | None
    lane: str | None
    workspace: str
    resume_run_id: int | None


# A runner takes one due fire and returns the run id it produced.
Runner = Callable[[ScheduledFire], int]


def _slug(target: str) -> str:
    """Filesystem-safe, stable per-target workspace slug."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", target).strip("-")
    return s or "target"


class Heartbeat:
    def __init__(
        self,
        store: MemoryStore,
        runner: Runner,
        *,
        workspace_root: str = os.path.join("workspace", "scheduled"),
    ):
        self.store = store
        self.runner = runner
        self.workspace_root = workspace_root

    # ----- registration (durable) ----------------------------------------

    def schedule(
        self,
        target: str,
        *,
        interval_seconds: float,
        goal: str = "",
        domain: str | None = None,
        lane: str | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        self.store.upsert_schedule(
            target,
            interval_seconds=interval_seconds,
            goal=goal,
            domain=domain,
            lane=lane,
        )

    def unschedule(self, target: str) -> bool:
        return self.store.remove_schedule(target)

    def entries(self) -> list[ScheduleEntry]:
        return self.store.schedules()

    def due(self, now: float) -> list[ScheduleEntry]:
        return [e for e in self.store.schedules() if self._is_due(e, now)]

    # ----- the tick -------------------------------------------------------

    def tick(self, now: float) -> list[int]:
        """Fire every due target once, in registration order, and return the run
        ids produced. A target that errors is recorded (its attempt is stamped so
        it does not hot-loop) and does **not** abort the rest of the tick."""
        fired: list[int] = []
        for entry in self.store.schedules():
            if not self._is_due(entry, now):
                continue
            fire = ScheduledFire(
                target=entry.target,
                goal=entry.goal or "",
                domain=entry.domain,
                lane=entry.lane,
                workspace=self._workspace_for(entry.target),
                resume_run_id=entry.last_run_id,
            )
            try:
                run_id = self.runner(fire)
            except Exception:
                # Failure isolation (R7 edge): stamp the attempt, keep the prior
                # resume anchor, continue with the remaining targets.
                self.store.mark_scheduled_fired(entry.target, now, entry.last_run_id)
                continue
            self.store.mark_scheduled_fired(entry.target, now, run_id)
            fired.append(run_id)
        return fired

    # ----- helpers --------------------------------------------------------

    def _is_due(self, entry: ScheduleEntry, now: float) -> bool:
        return entry.last_fired is None or (now - entry.last_fired) >= entry.interval_seconds

    def _workspace_for(self, target: str) -> str:
        return os.path.join(self.workspace_root, _slug(target))
