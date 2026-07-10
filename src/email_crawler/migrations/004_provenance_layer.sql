CREATE TABLE IF NOT EXISTS artifact_provenance (
    artifact_uid TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    seed_url TEXT NOT NULL,
    page_uid TEXT,
    artifact_value TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_run_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifact_provenance_type_value
ON artifact_provenance(artifact_type, artifact_value);

CREATE INDEX IF NOT EXISTS idx_artifact_provenance_page_uid
ON artifact_provenance(page_uid);

CREATE INDEX IF NOT EXISTS idx_artifact_provenance_last_run
ON artifact_provenance(last_run_id);
