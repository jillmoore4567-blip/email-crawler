# Historical Snapshots Design (Issue #5)

## Scope

Improve snapshot history fidelity and retrieval primitives while preserving backward compatibility for existing SQLite datasets.

## Retention Strategy

- Retention model: full-fidelity history, no compaction in v1.3.
- Rationale:
  - Historical comparisons are currently more valuable than storage reduction.
  - Existing datasets remain queryable without rewrite or archival steps.
  - Compaction can be introduced later behind explicit policy controls.

## Timeline Retrieval Primitives

- `load_page_snapshot_timeline(db_path, *, seed_url, page_url)`
  - Returns deterministic page snapshot history ordered by crawl completion time.
- `load_finding_snapshot_timeline(db_path, *, finding_type, finding_id)`
  - Returns deterministic finding status history ordered by crawl completion time.

## Indexing Improvements

- `idx_page_snapshots_page_id_last_seen`
- `idx_page_snapshots_run_id`
- `idx_finding_snapshots_type_id_run`

These indexes keep timeline retrieval bounded to indexed joins and lookups instead of repeated table scans.

## Performance Baseline

- Baseline fixture for Issue #5 uses a 12-run page history timeline in tests.
- Expected behavior:
  - deterministic ordering across repeated queries,
  - indexed lookups for page and finding histories,
  - no regression to existing snapshot diff workflows.

Measured large-history benchmark (local synthetic dataset):

- Dataset:
  - crawl runs: 120
  - pages per run: 40
  - total pages persisted: 4,800
  - page snapshots: 4,800
  - finding snapshots: 24,040
  - tracked page timeline rows: 120
  - tracked finding timeline rows: 120
- Query timings (milliseconds, 50 measured iterations after 5 warm-up iterations):
  - `load_page_snapshot_timeline`: mean 8.112, median 8.039, p95 9.018, min 7.205, max 9.410
  - `load_finding_snapshot_timeline`: mean 7.736, median 7.614, p95 8.674, min 6.573, max 10.285
- Environment:
  - OS: Windows 11 (10.0.22621)
  - Python: 3.14.6
  - CPU: Intel64 Family 6 Model 140 Stepping 1, 8 logical cores
  - Architecture: AMD64
- Methodology:
  - Single-process local benchmark against a synthetic SQLite dataset.
  - Timeline queries executed repeatedly for fixed tracked page/finding IDs.
  - Ordering path exercised with `ORDER BY completed_at ASC` plus snapshot ID tie-breakers.

## Backward Compatibility

- Migration `005_snapshot_timeline_indexes.sql` is additive only.
- Existing snapshot rows are preserved in place.
- Existing APIs (`compare_run_with_previous`, latest hash/link loaders) remain unchanged.