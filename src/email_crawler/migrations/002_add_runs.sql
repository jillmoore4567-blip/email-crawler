CREATE TABLE IF NOT EXISTS crawl_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    seed_url TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    crawler_version TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_crawl_runs_completed_at
ON crawl_runs(completed_at);