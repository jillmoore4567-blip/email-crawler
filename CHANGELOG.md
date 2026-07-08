# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,
and this project adheres to Semantic Versioning.

## [1.0.0] - 2026-07-08
### Added
- Plugin-based extractor registry with default built-in extractor registration.
- Snapshot comparison export to JSON and detailed page-level change metadata.
- Performance observability metrics in crawl results, stats output, and dashboard report.
- Migration fixture smoke testing with checked-in legacy SQLite fixture database.
- Documentation synchronization tests to prevent CLI/schema/docs drift.
- Benchmark harness for synthetic test site throughput, memory, and DB growth.
- Release-oriented CI stages for lint, type checks, migration tests, docs checks, and packaging checks.

### Improved
- Crawler internals now record detailed fetch, extraction, robots, and queue timings.
- Stats output now includes aggregate and per-seed performance telemetry.
- Dashboard includes performance observability cards and per-seed performance chart.
- Project metadata promoted to stable release quality with classifiers and license metadata.

### Fixed
- Legacy migration coverage now verifies preservation, ordering, idempotency, and final schema version.
- Docs checks now catch missing critical CLI options in release documentation.

### Performance
- Added reproducible benchmark output with throughput and memory telemetry for regression tracking.

### Security
- No known security fixes in this release.

### Migration Notes
- Existing legacy databases continue to migrate in-place through SQL migration chain.
- Final schema version for this release is `3`.
