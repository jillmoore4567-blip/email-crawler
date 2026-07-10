# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,
and this project adheres to Semantic Versioning.

## [Unreleased]

- No unreleased changes.

## [1.2.0] - 2026-07-09

Investigation-focused dashboard release that expands change analysis,
interactive reporting, and graph exploration without changing crawler
engine behavior or report output schemas.

### Added

- Interactive analytics dashboard panels for crawl metrics, email-domain
  distribution, document types, and crawl timing.
- Global table search/filter/sort and persistent dashboard filter state.
- Page Details panel with extracted artifacts and security-header context.
- Snapshot comparison table with page-level change filtering and sort.
- Page relationship graph using existing link graph data with:
  - force-directed and hierarchical layouts,
  - zoom/pan interactions,
  - seed/domain/depth/snapshot/link-type filters,
  - node click-through to existing page details,
  - internal vs external link edge coloring.
- Dashboard benchmark coverage for graph render latency on synthetic
  datasets (1k/5k/10k rows).
- Documentation page for graph visualization behavior and constraints.

### Improved

- Chart export supports PNG and SVG.
- Dashboard supports dark mode toggle and responsive/mobile layout.
- Integration tests assert presence of new dashboard and graph controls.

### Validation

- Ruff, mypy, and pytest all pass for release candidate.
- Dashboard benchmark remains below 200 ms threshold for all measured
  operations, including graph render latency.

## [1.0.0] - 2026-07-08

First stable release focused on observability, migration safety,
packaging quality, and release governance.

### Added

- Plugin-based extractor registry with deterministic built-in registration.
- Snapshot comparison export to JSON with detailed page-level change metadata.
- Performance observability metrics in crawl results, stats output, and HTML dashboard.
- Migration fixture smoke test using a checked-in legacy SQLite database fixture.
- Documentation synchronization tests to prevent CLI, schema, and docs drift.
- Benchmark harness and regression gate for throughput, memory, and DB growth.
- Release-oriented CI stages for lint, type checks, migration tests,
  docs checks, packaging, install verification, and benchmark
  regression checks.

### Improved

- Crawler internals now capture detailed fetch, extraction, robots, and queue timings.
- Stats output now includes aggregate and per-seed performance telemetry.
- Dashboard includes performance observability cards and per-seed charting.
- Packaging metadata and release validation are hardened for stable distribution.

### Fixed

- Legacy migration coverage now verifies preservation, ordering,
  idempotency, and latest schema version.
- Docs checks now catch missing critical CLI options in release documentation.
- Distribution packaging now explicitly includes SQL migration files.

### Performance

- Added reproducible benchmark output with throughput and memory
  telemetry for regression tracking.

### Security

- Project documentation now explicitly scopes usage to authorized
  defensive/security workflows.

### Migration Notes

- Existing legacy databases continue to migrate in-place through the
  ordered SQL migration chain.
- Final schema version for this release is 3.

### Backward Compatibility

- Existing CLI options are preserved.
- Existing migration path remains in-place and compatible with legacy databases.
