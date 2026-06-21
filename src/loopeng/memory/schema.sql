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
    finished    TEXT,                              -- ISO-8601 wall-clock end (proof-pack elapsed); nullable
    injected_learning_count INTEGER                -- reused prior learnings injected into this run's briefs (flywheel U5); nullable
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
    summary             TEXT NOT NULL,                 -- sanitized at write (flywheel R4)
    regression_test_ref TEXT,
    grade_delta         REAL                           -- grade-rank gain of the accepted fix; ranks cross-run reuse (flywheel U2); nullable for legacy rows
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

-- Fleet orchestration (plan-006 U1). A fleet run coordinates multiple loop items
-- under one goal; each item has a lifecycle status and a dependency list. Items
-- reference the per-target run they spawned (run_id) so the fleet report can
-- aggregate per-item single-run reports. New tables via CREATE TABLE IF NOT
-- EXISTS appear on the next open of an existing DB (no _migrate needed).
CREATE TABLE IF NOT EXISTS fleet_runs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    goal     TEXT,
    status   TEXT NOT NULL DEFAULT 'running',  -- running|converged|awaiting_human|stopped
    started  TEXT NOT NULL,                    -- ISO-8601, supplied by caller
    finished TEXT                              -- ISO-8601; nullable
);

CREATE TABLE IF NOT EXISTS fleet_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fleet_id        INTEGER NOT NULL REFERENCES fleet_runs(id),
    key             TEXT NOT NULL,             -- stable item key (also the worktree slug)
    status          TEXT NOT NULL DEFAULT 'pending',
    depends_on_json TEXT NOT NULL DEFAULT '[]',  -- list of upstream item keys
    target          TEXT,                      -- what this item runs on (URL/dir/spec); nullable for direct-add
    goal            TEXT,                      -- per-item goal; falls back to the fleet goal when null
    lane            TEXT,                      -- optional lane override (service|codebase); null = auto-route
    run_id          INTEGER,                   -- the per-target run this item spawned; nullable
    outcome_json    TEXT,                      -- routed outcome summary; nullable
    UNIQUE (fleet_id, key)
);

-- Fork-Card decision channel (plan 2026-06-17 U5). Append-only record of each
-- build decision the spec/northstar did not determine: what the agent emitted,
-- and how the supervisor resolved it. Like `confirmations`, this is an audit
-- trail surfaced at end-review; resolution never auto-reverses outside the loop.
-- New table via CREATE TABLE IF NOT EXISTS -> appears on next open (no _migrate).
CREATE TABLE IF NOT EXISTS fork_cards (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         INTEGER NOT NULL REFERENCES runs(id),
    iteration_id   INTEGER,                          -- iteration index n; nullable
    card_id        TEXT NOT NULL,                    -- the agent-assigned fork id
    options_json   TEXT NOT NULL DEFAULT '[]',       -- enumerated options
    spec_clause    TEXT,
    chosen_default TEXT,                             -- option id the agent built on; nullable
    reversibility  TEXT,
    blast_radius   TEXT,
    basis          TEXT,                             -- citation refs (json) or 'unresolved'
    decision       TEXT,                             -- keep_default|reverse|escalate|recorded
    chosen_option  TEXT,                             -- resolver's chosen option id; nullable
    created        TEXT                              -- ISO-8601, supplied by caller; nullable
);

CREATE INDEX IF NOT EXISTS idx_iterations_run ON iterations(run_id, n);
CREATE INDEX IF NOT EXISTS idx_learnings_run ON learnings(run_id);
CREATE INDEX IF NOT EXISTS idx_confirmations_run ON confirmations(run_id);
CREATE INDEX IF NOT EXISTS idx_fleet_items_fleet ON fleet_items(fleet_id);
CREATE INDEX IF NOT EXISTS idx_fork_cards_run ON fork_cards(run_id);
