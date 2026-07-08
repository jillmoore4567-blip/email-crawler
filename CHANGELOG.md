# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,
and this project adheres to Semantic Versioning.

## [Unreleased]

- No unreleased changes.

## [1.0.0] - 2026-07-08

First stable release focused on observability, migration safety, packaging quality, and release governance.

### Added

- Plugin-based extractor registry with deterministic built-in registration.
- Snapshot comparison export to JSON with detailed page-level change metadata.
- Performance observability metrics in crawl results, stats output, and HTML dashboard.
- Migration fixture smoke test using a checked-in legacy SQLite database fixture.
- Documentation synchronization tests to prevent CLI, schema, and docs drift.
- Benchmark harness and regression gate for throughput, memory, and DB growth.
- Release-oriented CI stages for lint, type checks, migration tests, docs checks, packaging, install verification, and benchmark regression checks.

### Improved

- Crawler internals now capture detailed fetch, extraction, robots, and queue timings.
- Stats output now includes aggregate and per-seed performance telemetry.
- Dashboard includes performance observability cards and per-seed charting.
- Packaging metadata and release validation are hardened for stable distribution.

### Fixed

- Legacy migration coverage now verifies preservation, ordering, idempotency, and latest schema version.
- Docs checks now catch missing critical CLI options in release documentation.
- Distribution packaging now explicitly includes SQL migration files.

### Performance

- Added reproducible benchmark output with throughput and memory telemetry for regression tracking.

### Security

- Project documentation now explicitly scopes usage to authorized defensive/security workflows.

### Migration Notes

- Existing legacy databases continue to migrate in-place through the ordered SQL migration chain.
- Final schema version for this release is 3.

### Backward Compatibility

- Existing CLI options are preserved.
- Existing migration path remains in-place and compatible with legacy databases.
