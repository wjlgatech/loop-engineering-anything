-- loop-engineering-anything memory schema (U2, R6).
-- Local-first run history enabling cross-run "transcendent" queries
-- (trend, plateau, recurring failures) the Printing-Press SQLite pattern.

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target      TEXT NOT NULL,
    lane        TEXT NOT NULL,
    goal        TEXT,
    status      TEXT NOT NULL DEFAULT 'running',  -- running|converged|blocked_safety|stopped
    final_grade TEXT,
    started     TEXT NOT NULL                      -- ISO-8601, supplied by caller
);

CREATE TABLE IF NOT EXISTS iterations (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id               INTEGER NOT NULL REFERENCES runs(id),
    n                    INTEGER NOT NULL,          -- iteration index within the run
    grade                TEXT NOT NULL,
    dims_json            TEXT NOT NULL,             -- per-dimension scores
    failing_fixtures_json TEXT NOT NULL DEFAULT '[]',
    safety_ok            INTEGER NOT NULL,          -- 0/1
    token_cost           INTEGER,                   -- nullable: advisory until a source is wired
    diff_ref             TEXT,                      -- path/sha of the applied diff (data only, never executed)
    UNIQUE (run_id, n)
);

CREATE TABLE IF NOT EXISTS learnings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES runs(id),
    iteration_id        INTEGER REFERENCES iterations(id),
    summary             TEXT NOT NULL,
    regression_test_ref TEXT
);

CREATE INDEX IF NOT EXISTS idx_iterations_run ON iterations(run_id, n);
CREATE INDEX IF NOT EXISTS idx_learnings_run ON learnings(run_id);
