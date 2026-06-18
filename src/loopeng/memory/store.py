"""SQLite memory store (U2, R6; concurrency hardened U16, R9).

Originally single-writer: the loop controller is single-threaded, so the MVP
needed no concurrency guard. Worktree parallelism (U16) changes that -- several
loops fan out concurrently and each records its own run/iterations into the same
store. SQLite serializes writes itself, but concurrent writers on the *default*
threading guard would raise ``ProgrammingError`` (a connection used off its
creating thread) or contend into ``database is locked``.

Decision (plan-004 U16): make this one store object safe to share across threads
by **serializing every write through a single shared connection guarded by a
re-entrant lock, in WAL mode**. Concretely:
  - ``check_same_thread=False`` so the shared connection can be used from worker
    threads (we provide our own mutual exclusion rather than per-thread conns).
  - WAL journal mode + ``busy_timeout`` so a reader never blocks a writer.
  - An ``RLock`` (``_wlock``) wraps every statement+commit so writes from
    parallel runs are applied one-at-a-time and never interleave/corrupt. Reads
    take the same lock so a row is never read mid-write.
This keeps a single writer *connection* (the plan's named decision) while letting
N parallel loops record independently.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .fleet_state import (
    FleetItem,
    FleetItemStatus,
    FleetRun,
    FleetRunStatus,
    assert_item_transition,
)

_SCHEMA = Path(__file__).with_name("schema.sql")

# Grade ranking for trend/plateau math. CLI-Judge grades A-F (no E in the
# standard scheme); E is mapped defensively in case a suite emits it.
GRADE_RANK = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0}


def grade_rank(grade: str) -> int:
    """Numeric rank for a letter grade; unknown grades rank lowest."""
    return GRADE_RANK.get((grade or "").strip().upper(), -1)


@dataclass
class Run:
    id: int
    target: str
    lane: str
    goal: str | None
    status: str
    final_grade: str | None
    started: str
    finished: str | None = None


@dataclass
class ScheduleEntry:
    """A durably-registered scheduled target (U14, R7)."""

    target: str
    goal: str | None
    domain: str | None
    lane: str | None
    interval_seconds: float
    last_fired: float | None
    last_run_id: int | None  # advisory resume anchor (not an enforced FK)


@dataclass
class Iteration:
    id: int
    run_id: int
    n: int
    grade: str
    dims: dict
    failing_fixtures: list
    safety_ok: bool
    token_cost: int | None
    diff_ref: str | None
    score: float | None = None


@dataclass
class ForkCardRecord:
    """A persisted Fork-Card + its supervisor resolution (plan 2026-06-17 U5)."""

    id: int
    run_id: int
    iteration_id: int | None
    card_id: str
    options: list
    spec_clause: str | None
    chosen_default: str | None
    reversibility: str | None
    blast_radius: str | None
    basis: Any
    decision: str | None
    chosen_option: str | None
    created: str | None


class MemoryStore:
    def __init__(self, path: str | Path = "loopeng.db"):
        self.path = str(path)
        # check_same_thread=False: we share one connection across worker threads
        # (U16 fan-out) and provide our own mutual exclusion via ``_wlock`` below,
        # so SQLite's per-thread guard would only get in the way. Every write and
        # read goes through that lock, so the connection is never touched
        # concurrently.
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Re-entrant: a few public methods call other locked methods (e.g.
        # is_plateaued -> score_trajectory -> iterations).
        self._wlock = threading.RLock()
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        # A writer holding the lock + WAL means readers don't block; the timeout
        # is a belt-and-braces guard against any lock contention.
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA.read_text())
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Additive, idempotent migrations for DBs created before a column existed.

        ``CREATE TABLE IF NOT EXISTS`` won't add columns to a pre-existing table,
        so add any missing nullable columns here (proof-pack ``runs.finished``).
        """
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(runs)").fetchall()}
        if "finished" not in cols:
            self._conn.execute("ALTER TABLE runs ADD COLUMN finished TEXT")
        it_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(iterations)").fetchall()}
        if "score" not in it_cols:
            self._conn.execute("ALTER TABLE iterations ADD COLUMN score REAL")

    @classmethod
    def default(cls) -> "MemoryStore":
        return cls("loopeng.db")

    def close(self) -> None:
        with self._wlock:
            self._conn.close()

    # ----- runs -----------------------------------------------------------

    def create_run(self, target: str, lane: str, goal: str | None, started: str) -> int:
        with self._wlock:
            cur = self._conn.execute(
                "INSERT INTO runs (target, lane, goal, status, started) VALUES (?, ?, ?, 'running', ?)",
                (target, lane, goal, started),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, final_grade: str | None) -> None:
        with self._wlock:
            self._conn.execute(
                "UPDATE runs SET status = ?, final_grade = ? WHERE id = ?",
                (status, final_grade, run_id),
            )
            self._conn.commit()

    def record_finished(self, run_id: int, finished: str) -> None:
        """Stamp the run's wall-clock end (ISO-8601). Set by the runner after
        ``controller.run`` returns, since ``finish_run`` fires inside the
        controller and the runner owns the elapsed measurement (proof-pack)."""
        with self._wlock:
            self._conn.execute("UPDATE runs SET finished = ? WHERE id = ?", (finished, run_id))
            self._conn.commit()

    def get_run(self, run_id: int) -> Run | None:
        with self._wlock:
            row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def list_runs(self) -> list[Run]:
        with self._wlock:
            rows = self._conn.execute("SELECT * FROM runs ORDER BY id DESC").fetchall()
        return [self._row_to_run(r) for r in rows]

    # ----- iterations -----------------------------------------------------

    def record_iteration(
        self,
        run_id: int,
        n: int,
        grade: str,
        dims: dict,
        safety_ok: bool,
        failing_fixtures: list | None = None,
        token_cost: int | None = None,
        diff_ref: str | None = None,
        score: float | None = None,
    ) -> int:
        with self._wlock:
            cur = self._conn.execute(
                """INSERT INTO iterations
                   (run_id, n, grade, score, dims_json, failing_fixtures_json, safety_ok, token_cost, diff_ref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    n,
                    grade,
                    score,
                    json.dumps(dims),
                    json.dumps(failing_fixtures or []),
                    1 if safety_ok else 0,
                    token_cost,
                    diff_ref,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def iterations(self, run_id: int) -> list[Iteration]:
        with self._wlock:
            rows = self._conn.execute(
                "SELECT * FROM iterations WHERE run_id = ? ORDER BY n", (run_id,)
            ).fetchall()
        return [self._row_to_iteration(r) for r in rows]

    # ----- learnings ------------------------------------------------------

    def record_learning(
        self, run_id: int, iteration_id: int | None, summary: str, regression_test_ref: str | None = None
    ) -> int:
        with self._wlock:
            cur = self._conn.execute(
                "INSERT INTO learnings (run_id, iteration_id, summary, regression_test_ref) VALUES (?, ?, ?, ?)",
                (run_id, iteration_id, summary, regression_test_ref),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def learnings(self, run_id: int) -> list[dict]:
        with self._wlock:
            rows = self._conn.execute(
                "SELECT * FROM learnings WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ----- confirmations (human-confirm gate audit, U5) -------------------

    def record_confirmation(
        self, run_id: int, confirmed: bool, reason: str | None = None, created: str | None = None
    ) -> int:
        """Persist a human verdict at the verification gate (U5, KTD5).

        Audit-only: this write is never read back into the gate's ``confirmed``
        input, so a recorded approval cannot become an auto-ship. ``confirm_convergence``
        remains the sole shippability authority.
        """
        with self._wlock:
            cur = self._conn.execute(
                "INSERT INTO confirmations (run_id, confirmed, reason, created) VALUES (?, ?, ?, ?)",
                (run_id, 1 if confirmed else 0, reason, created),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def confirmations(self, run_id: int) -> list[dict]:
        with self._wlock:
            rows = self._conn.execute(
                "SELECT * FROM confirmations WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
        return [{**dict(r), "confirmed": bool(r["confirmed"])} for r in rows]

    # ----- fork cards (decision channel audit trail, plan 2026-06-17 U5) ---

    def record_fork_card(
        self,
        run_id: int,
        *,
        card_id: str,
        options: list | None = None,
        spec_clause: str | None = None,
        chosen_default: str | None = None,
        reversibility: str | None = None,
        blast_radius: str | None = None,
        basis: Any = None,
        decision: str | None = None,
        chosen_option: str | None = None,
        iteration_id: int | None = None,
        created: str | None = None,
    ) -> int:
        """Persist one Fork-Card and its resolution (append-only audit, KTD5).

        Takes decomposed primitives rather than a ``ForkCard`` so the store stays
        free of a ``loop`` import (the controller decomposes the card). ``options``
        and ``basis`` are JSON-encoded; the read path decodes them.
        """
        with self._wlock:
            cur = self._conn.execute(
                "INSERT INTO fork_cards (run_id, iteration_id, card_id, options_json, "
                "spec_clause, chosen_default, reversibility, blast_radius, basis, decision, "
                "chosen_option, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    iteration_id,
                    card_id,
                    json.dumps(options or []),
                    spec_clause,
                    chosen_default,
                    reversibility,
                    blast_radius,
                    json.dumps(basis),
                    decision,
                    chosen_option,
                    created,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def fork_cards(self, run_id: int) -> list[ForkCardRecord]:
        with self._wlock:
            rows = self._conn.execute(
                "SELECT * FROM fork_cards WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
        return [self._row_to_fork_card(r) for r in rows]

    @staticmethod
    def _row_to_fork_card(r) -> ForkCardRecord:
        return ForkCardRecord(
            id=r["id"],
            run_id=r["run_id"],
            iteration_id=r["iteration_id"],
            card_id=r["card_id"],
            options=json.loads(r["options_json"]) if r["options_json"] else [],
            spec_clause=r["spec_clause"],
            chosen_default=r["chosen_default"],
            reversibility=r["reversibility"],
            blast_radius=r["blast_radius"],
            basis=json.loads(r["basis"]) if r["basis"] is not None else None,
            decision=r["decision"],
            chosen_option=r["chosen_option"],
            created=r["created"],
        )

    # ----- scheduler state (U14) -----------------------------------------

    def upsert_schedule(
        self,
        target: str,
        *,
        interval_seconds: float,
        goal: str | None = None,
        domain: str | None = None,
        lane: str | None = None,
    ) -> None:
        """Register or update a scheduled target's cadence, preserving its
        ``last_fired``/``last_run_id`` resume anchor across re-registration."""
        with self._wlock:
            updated = self._conn.execute(
                """UPDATE schedule_state
                   SET goal = ?, domain = ?, lane = ?, interval_seconds = ?
                   WHERE target = ?""",
                (goal, domain, lane, interval_seconds, target),
            )
            if updated.rowcount == 0:
                self._conn.execute(
                    """INSERT INTO schedule_state
                       (target, goal, domain, lane, interval_seconds, last_fired, last_run_id)
                       VALUES (?, ?, ?, ?, ?, NULL, NULL)""",
                    (target, goal, domain, lane, interval_seconds),
                )
            self._conn.commit()

    def schedules(self) -> list[ScheduleEntry]:
        with self._wlock:
            rows = self._conn.execute(
                "SELECT * FROM schedule_state ORDER BY target"
            ).fetchall()
        return [self._row_to_schedule(r) for r in rows]

    def remove_schedule(self, target: str) -> bool:
        with self._wlock:
            cur = self._conn.execute("DELETE FROM schedule_state WHERE target = ?", (target,))
            self._conn.commit()
            return cur.rowcount > 0

    def mark_scheduled_fired(self, target: str, last_fired: float, last_run_id: int | None) -> None:
        with self._wlock:
            self._conn.execute(
                "UPDATE schedule_state SET last_fired = ?, last_run_id = ? WHERE target = ?",
                (last_fired, last_run_id, target),
            )
            self._conn.commit()

    # ----- fleet orchestration (plan-006 U1) ------------------------------

    def create_fleet(self, goal: str | None, started: str) -> int:
        with self._wlock:
            cur = self._conn.execute(
                "INSERT INTO fleet_runs (goal, status, started) VALUES (?, 'running', ?)",
                (goal, started),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def set_fleet_status(
        self, fleet_id: int, status: FleetRunStatus | str, finished: str | None = None
    ) -> None:
        with self._wlock:
            self._conn.execute(
                "UPDATE fleet_runs SET status = ?, finished = ? WHERE id = ?",
                (FleetRunStatus(status).value, finished, fleet_id),
            )
            self._conn.commit()

    def get_fleet(self, fleet_id: int) -> FleetRun | None:
        with self._wlock:
            row = self._conn.execute("SELECT * FROM fleet_runs WHERE id = ?", (fleet_id,)).fetchone()
        return self._row_to_fleet(row) if row else None

    def add_fleet_item(
        self,
        fleet_id: int,
        key: str,
        depends_on: list | None = None,
        *,
        target: str | None = None,
        goal: str | None = None,
        lane: str | None = None,
    ) -> int:
        with self._wlock:
            cur = self._conn.execute(
                "INSERT INTO fleet_items (fleet_id, key, status, depends_on_json, target, goal, lane) "
                "VALUES (?, ?, 'pending', ?, ?, ?, ?)",
                (fleet_id, key, json.dumps(list(depends_on or [])), target, goal, lane),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def set_item_status(
        self, item_id: int, status: FleetItemStatus | str, *, run_id: int | None = None
    ) -> None:
        """Transition a fleet item to ``status``, enforcing the legal-transition
        guard (U1) so every persisted change is legal by construction. ``run_id``
        is set when a worker run is (re)spawned for the item."""
        dst = FleetItemStatus(status)
        with self._wlock:
            row = self._conn.execute(
                "SELECT status FROM fleet_items WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"no fleet item {item_id}")
            assert_item_transition(FleetItemStatus(row["status"]), dst)
            if run_id is not None:
                self._conn.execute(
                    "UPDATE fleet_items SET status = ?, run_id = ? WHERE id = ?",
                    (dst.value, run_id, item_id),
                )
            else:
                self._conn.execute(
                    "UPDATE fleet_items SET status = ? WHERE id = ?", (dst.value, item_id)
                )
            self._conn.commit()

    def record_item_outcome(self, item_id: int, outcome: dict) -> None:
        with self._wlock:
            self._conn.execute(
                "UPDATE fleet_items SET outcome_json = ? WHERE id = ?",
                (json.dumps(outcome), item_id),
            )
            self._conn.commit()

    def fleet_items(self, fleet_id: int) -> list[FleetItem]:
        with self._wlock:
            rows = self._conn.execute(
                "SELECT * FROM fleet_items WHERE fleet_id = ? ORDER BY id", (fleet_id,)
            ).fetchall()
        return [self._row_to_fleet_item(r) for r in rows]

    def escalations(self, fleet_id: int) -> list[FleetItem]:
        """Only the items awaiting a human (status escalated) for this fleet."""
        return [i for i in self.fleet_items(fleet_id) if i.status is FleetItemStatus.ESCALATED]

    # ----- transcendent queries ------------------------------------------

    def grade_trajectory(self, run_id: int) -> list[str]:
        """Ordered list of grades across the run's iterations (R6 trend)."""
        return [it.grade for it in self.iterations(run_id)]

    def score_trajectory(self, run_id: int) -> list[float | None]:
        """Ordered list of continuous scores across the run's iterations (U10).

        Entries are ``None`` for legacy rows written before the score column.
        """
        return [it.score for it in self.iterations(run_id)]

    def is_plateaued(
        self, run_id: int, patience: int, *, on_score: bool = False, since_iteration: int = 0
    ) -> bool:
        """True if the last ``patience`` iterations did not beat the best value
        achieved before that window. Needs more than ``patience`` iterations to
        evaluate -- fewer means not plateaued.

        ``on_score`` selects the trajectory used for the no-gain test: by default
        the letter-grade ladder (unchanged software behavior, R2); when a domain
        runs under a continuous score target, the persisted ``score`` column so a
        score-only domain plateaus on real reward instead of a constant projected
        grade rank (U10/KTD4). Falls back to grades if any score is unrecorded.

        ``since_iteration`` drops that many leading iterations before the no-gain
        test (U2). A plateau pivot sets it to the iteration count at pivot time so
        the post-pivot strategy is judged over its own window -- the pre-pivot best
        is intentionally excluded, giving the new strategy ``patience`` clean
        iterations before it can stop the loop.
        """
        if on_score:
            scores = self.score_trajectory(run_id)
            if scores and all(s is not None for s in scores):
                values: list[float] = scores  # type: ignore[assignment]
            else:
                values = [grade_rank(g) for g in self.grade_trajectory(run_id)]
        else:
            values = [grade_rank(g) for g in self.grade_trajectory(run_id)]
        if since_iteration > 0:
            values = values[since_iteration:]
        if patience < 1 or len(values) <= patience:
            return False
        best_before = max(values[:-patience])
        recent_best = max(values[-patience:])
        return recent_best <= best_before

    def recurring_failures(
        self, min_runs: int = 2, *, target: str | None = None
    ) -> list[tuple[str, int]]:
        """Fixtures that fail across at least ``min_runs`` distinct runs.

        Returns (fixture, distinct_run_count) sorted by frequency. Joins failing
        fixtures across history -- a query a stateless run cannot answer.

        ``target`` scopes the join to runs against one target (join through
        ``runs.target``), so a target's cross-run history never leaks into an
        unrelated target's brief (U1). The unscoped form (``target=None``) keeps
        the original transcendent query for reporting across all runs.
        """
        counts: dict[str, set[int]] = {}
        with self._wlock:
            if target is None:
                rows = self._conn.execute(
                    "SELECT run_id, failing_fixtures_json FROM iterations"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT i.run_id AS run_id, i.failing_fixtures_json AS failing_fixtures_json "
                    "FROM iterations i JOIN runs r ON i.run_id = r.id WHERE r.target = ?",
                    (target,),
                ).fetchall()
        for row in rows:
            for fixture in json.loads(row["failing_fixtures_json"]):
                counts.setdefault(fixture, set()).add(row["run_id"])
        result = [(fx, len(runs)) for fx, runs in counts.items() if len(runs) >= min_runs]
        return sorted(result, key=lambda x: (-x[1], x[0]))

    # ----- row mappers ----------------------------------------------------

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> Run:
        return Run(
            id=row["id"],
            target=row["target"],
            lane=row["lane"],
            goal=row["goal"],
            status=row["status"],
            final_grade=row["final_grade"],
            started=row["started"],
            finished=row["finished"],
        )

    @staticmethod
    def _row_to_schedule(row: sqlite3.Row) -> ScheduleEntry:
        return ScheduleEntry(
            target=row["target"],
            goal=row["goal"],
            domain=row["domain"],
            lane=row["lane"],
            interval_seconds=row["interval_seconds"],
            last_fired=row["last_fired"],
            last_run_id=row["last_run_id"],
        )

    @staticmethod
    def _row_to_fleet(row: sqlite3.Row) -> FleetRun:
        return FleetRun(
            id=row["id"],
            goal=row["goal"],
            status=FleetRunStatus(row["status"]),
            started=row["started"],
            finished=row["finished"],
        )

    @staticmethod
    def _row_to_fleet_item(row: sqlite3.Row) -> FleetItem:
        keys = row.keys()
        return FleetItem(
            id=row["id"],
            fleet_id=row["fleet_id"],
            key=row["key"],
            status=FleetItemStatus(row["status"]),
            depends_on=json.loads(row["depends_on_json"]),
            target=row["target"] if "target" in keys else None,
            goal=row["goal"] if "goal" in keys else None,
            lane=row["lane"] if "lane" in keys else None,
            run_id=row["run_id"],
            outcome=json.loads(row["outcome_json"]) if row["outcome_json"] else None,
        )

    @staticmethod
    def _row_to_iteration(row: sqlite3.Row) -> Iteration:
        return Iteration(
            id=row["id"],
            run_id=row["run_id"],
            n=row["n"],
            grade=row["grade"],
            dims=json.loads(row["dims_json"]),
            failing_fixtures=json.loads(row["failing_fixtures_json"]),
            safety_ok=bool(row["safety_ok"]),
            token_cost=row["token_cost"],
            diff_ref=row["diff_ref"],
            score=row["score"],
        )
