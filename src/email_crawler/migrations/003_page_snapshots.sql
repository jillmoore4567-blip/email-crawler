CREATE TABLE IF NOT EXISTS page_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_id INTEGER NOT NULL,
    content_hash TEXT,
    http_status INTEGER,
    title TEXT,
    last_seen TEXT NOT NULL,
    UNIQUE(run_id, page_id)
);

CREATE TABLE IF NOT EXISTS finding_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(run_id, finding_type, finding_id)
);

CREATE INDEX IF NOT EXISTS idx_finding_snapshots_type
ON finding_snapshots(finding_type, status);