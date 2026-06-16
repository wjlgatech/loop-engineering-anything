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
    started     TEXT NOT NULL,                     -- ISO-8601, supplied by caller
    finished    TEXT                               -- ISO-8601 wall-clock end (proof-pack elapsed); nullable
);

CREATE TABLE IF NOT EXISTS iterations (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id               INTEGER NOT NULL REFERENCES runs(id),
    n                    INTEGER NOT NULL,          -- iteration index within the run
    grade                TEXT NOT NULL,             -- coarse letter (every domain projects onto it, KTD1)
    score                REAL,                      -- primary continuous signal; nullable for legacy rows (U9)
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

-- Durable scheduler state (U14, R7): a registered target's cadence survives a
-- process restart ("going to the beach" -> "always running"). last_fired +
-- last_run_id are the resume anchor so a wake-up continues from the recorded run.
CREATE TABLE IF NOT EXISTS schedule_state (
    target           TEXT PRIMARY KEY,
    goal             TEXT,
    domain           TEXT,                          -- forced domain name; nullable
    lane             TEXT,                          -- forced lane; nullable
    interval_seconds REAL NOT NULL,
    last_fired       REAL,                          -- epoch seconds; NULL = never fired
    last_run_id      INTEGER                         -- advisory resume anchor; nullable
);

-- Human-confirm gate audit trail (U5, R10). When the verification gate requires
-- confirmation for a CONVERGED outcome, the human's verdict + the firing reason
-- are recorded here for audit. This table is WRITE-ONLY with respect to
-- shippability: nothing reads it back into the gate's `confirmed` input, so a
-- recorded approval can never become an auto-ship (KTD5).
CREATE TABLE IF NOT EXISTS confirmations (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    INTEGER NOT NULL REFERENCES runs(id),
    confirmed INTEGER NOT NULL,                       -- 0/1 the human's approve/reject
    reason    TEXT,                                   -- why the gate fired (borderline dim/score)
    created   TEXT                                    -- ISO-8601, supplied by caller; nullable
);

CREATE INDEX IF NOT EXISTS idx_iterations_run ON iterations(run_id, n);
CREATE INDEX IF NOT EXISTS idx_learnings_run ON learnings(run_id);
CREATE INDEX IF NOT EXISTS idx_confirmations_run ON confirmations(run_id);
