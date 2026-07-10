# Provenance Layer Design (Issue #4)

## Scope

Introduce stable identifiers and lifecycle timestamps for runs, pages, and
extracted artifacts while preserving current CLI/report behavior and existing
SQLite compatibility.

## Database Schema Changes

1. `crawl_runs`
   Add `run_uid TEXT` (stable run identifier), backfill existing rows with
   `run_id`, and add a unique index on `run_uid`.

2. `pages`
   Add `page_uid TEXT` (stable page identifier across runs), add `first_seen`
   and `last_seen`, and add indexes on `page_uid` and `(seed_url, page_uid)`.

3. New table: `artifact_provenance`
   Columns: `artifact_uid TEXT PRIMARY KEY`, `artifact_type TEXT NOT NULL`,
   `seed_url TEXT NOT NULL`, `page_uid TEXT`, `artifact_value TEXT NOT NULL`,
   `first_seen TEXT NOT NULL`, `last_seen TEXT NOT NULL`,
   `last_run_id TEXT NOT NULL`. Indexes: `(artifact_type, artifact_value)`,
   `page_uid`, and `last_run_id`.

### Canonical Intelligence Provenance Model

- Canonical artifact type: `intelligence`.
- Canonical artifact value: `<url>|<finding_type>`.

Why this model is preferred:

- Matches existing `finding_snapshots` key shape for intelligence entries.
- Avoids split namespaces (`intel:*` vs `intelligence`) that can fragment
   lifecycle continuity.
- Preserves subtype granularity without introducing additional schema.

## Migration Strategy

- Add migration `004_provenance.sql`.
- Migration is additive only (no destructive operations).

Backfill:

- `crawl_runs.run_uid = run_id`
- `pages.page_uid = sha256(seed_url + "|" + url)`
- `pages.first_seen/last_seen = crawled_at` when missing
- Normalize legacy intelligence provenance rows into canonical
   `intelligence + <url>|<finding_type>` where possible.

- Keep older tables and constraints unchanged.

## Backward Compatibility

- Existing databases migrate forward automatically through `_apply_migrations`.
- Existing output files and report schema remain unchanged (`stats.json`,
  `snapshot_diff.json`, HTML report).
- Existing run IDs remain valid and continue as primary compatibility key.

## Performance Considerations

- Use deterministic hash IDs (`sha256`) computed in Python once per entity.
- Upsert artifact provenance with indexed primary key (`artifact_uid`) to keep
   writes O(log n).
- Keep additional SELECT/UPDATE queries bounded to indexed fields.
- No change to crawl network path; only persistence-layer overhead.

## Testing Plan

1. Migration tests:
   Verify schema version increments to 4 and legacy DB migration preserves old
   rows while backfilling new provenance columns.

2. Provenance correctness tests:
   Verify `first_seen` is immutable over subsequent runs, `last_seen` advances
   for observed pages/artifacts, and `page_uid` plus `artifact_uid` remain
   stable across runs.

3. Integration regression:
   Verify existing end-to-end CLI/report tests remain green and snapshot
   comparison logic shows no behavior regressions.

## Incremental Implementation Plan

1. Add migration and storage helpers for stable IDs + lifecycle timestamps.
2. Wire provenance writes into `persist_results_sqlite` and unchanged-page
   carry-forward path.
3. Add/adjust unit tests and migration fixtures.
4. Update documentation (`README` + provenance model doc).
5. Run Ruff, mypy, pytest after major code changes.
