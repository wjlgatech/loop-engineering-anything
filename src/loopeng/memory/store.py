"""SQLite memory store (U2, R6).

Single-writer by design: the loop controller is single-threaded (one iteration
runs, writes, then advances), so no concurrency guard is needed for the MVP.
WAL is enabled as cheap forward-compatibility for the deferred parallel-looping
feature; until then the store has exactly one writer.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

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


class MemoryStore:
    def __init__(self, path: str | Path = "loopeng.db"):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
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
        self._conn.close()

    # ----- runs -----------------------------------------------------------

    def create_run(self, target: str, lane: str, goal: str | None, started: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO runs (target, lane, goal, status, started) VALUES (?, ?, ?, 'running', ?)",
            (target, lane, goal, started),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, final_grade: str | None) -> None:
        self._conn.execute(
            "UPDATE runs SET status = ?, final_grade = ? WHERE id = ?",
            (status, final_grade, run_id),
        )
        self._conn.commit()

    def record_finished(self, run_id: int, finished: str) -> None:
        """Stamp the run's wall-clock end (ISO-8601). Set by the runner after
        ``controller.run`` returns, since ``finish_run`` fires inside the
        controller and the runner owns the elapsed measurement (proof-pack)."""
        self._conn.execute("UPDATE runs SET finished = ? WHERE id = ?", (finished, run_id))
        self._conn.commit()

    def get_run(self, run_id: int) -> Run | None:
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def list_runs(self) -> list[Run]:
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
        rows = self._conn.execute(
            "SELECT * FROM iterations WHERE run_id = ? ORDER BY n", (run_id,)
        ).fetchall()
        return [self._row_to_iteration(r) for r in rows]

    # ----- learnings ------------------------------------------------------

    def record_learning(
        self, run_id: int, iteration_id: int | None, summary: str, regression_test_ref: str | None = None
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO learnings (run_id, iteration_id, summary, regression_test_ref) VALUES (?, ?, ?, ?)",
            (run_id, iteration_id, summary, regression_test_ref),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def learnings(self, run_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM learnings WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ----- transcendent queries ------------------------------------------

    def grade_trajectory(self, run_id: int) -> list[str]:
        """Ordered list of grades across the run's iterations (R6 trend)."""
        return [it.grade for it in self.iterations(run_id)]

    def is_plateaued(self, run_id: int, patience: int) -> bool:
        """True if the last ``patience`` iterations did not beat the best grade
        achieved before that window. Needs more than ``patience`` iterations to
        evaluate -- fewer means not plateaued."""
        grades = [grade_rank(g) for g in self.grade_trajectory(run_id)]
        if patience < 1 or len(grades) <= patience:
            return False
        best_before = max(grades[:-patience])
        recent_best = max(grades[-patience:])
        return recent_best <= best_before

    def recurring_failures(self, min_runs: int = 2) -> list[tuple[str, int]]:
        """Fixtures that fail across at least ``min_runs`` distinct runs.

        Returns (fixture, distinct_run_count) sorted by frequency. Joins failing
        fixtures across the full history -- a query a stateless run cannot answer.
        """
        counts: dict[str, set[int]] = {}
        rows = self._conn.execute(
            "SELECT run_id, failing_fixtures_json FROM iterations"
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
