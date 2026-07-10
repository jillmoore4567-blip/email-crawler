CREATE INDEX IF NOT EXISTS idx_page_snapshots_page_id_last_seen
ON page_snapshots(page_id, last_seen);

CREATE INDEX IF NOT EXISTS idx_page_snapshots_run_id
ON page_snapshots(run_id);

CREATE INDEX IF NOT EXISTS idx_finding_snapshots_type_id_run
ON finding_snapshots(finding_type, finding_id, run_id);