# Release Notes v1.0.0

## Added
- Incremental crawling.
- Historical snapshots and snapshot diff export.
- SQLite migrations and compatibility-safe migration runner.
- Plugin architecture for extractors.
- HTML reporting dashboard and machine-readable exports.
- Benchmark harness and regression checker.
- CI pipeline with lint, type checks, migration checks, packaging checks, and tests.

## Improved
- Observability and telemetry coverage for crawl performance.
- Type safety with staged strict mypy gating.
- Packaging metadata and release artifact validation.
- Documentation quality and drift checks.

## Fixed
- Migration compatibility edge cases for legacy databases.
- Report generation and synchronization with snapshot diff payloads.
- Coverage gaps in integration and migration test paths.

## Compatibility
- Existing CLI options are preserved.
- Existing migration chain remains in-place and backward compatible.
- Final schema version for this release: 3.
