# Architecture Summary

## High-Level Flow

1. CLI reads configuration and seeds.
2. Async crawler performs bounded BFS crawling with extraction plugins.
3. Findings are persisted to SQLite with migration-managed schema.
4. Snapshot diffing compares current and previous runs.
5. Reporting layer builds JSON payload and HTML dashboard.
6. Benchmarks and CI gates validate performance and correctness.

## Core Modules

- `src/email_crawler/cli.py`: entrypoint and pipeline orchestration.
- `src/email_crawler/crawler.py`: async crawl engine and extraction lifecycle.
- `src/email_crawler/extractors/`: plugin registry and extraction components.
- `src/email_crawler/storage.py`: persistence, run history, and snapshot diff logic.
- `src/email_crawler/reporting.py`: HTML dashboard and analysis payload shaping.
- `src/email_crawler/dashboard_benchmark.py`: synthetic UI performance benchmark model.

## Supporting Components

- `scripts/benchmark_synthetic.py`: synthetic crawl benchmark runner.
- `scripts/benchmark_dashboard.py`: dashboard benchmark runner.
- `scripts/check_benchmark_regression.py`: benchmark threshold regression gate.
- `tests/`: unit, integration, migration, docs-sync, and benchmark tests.
- `.github/workflows/ci.yml`: automated lint/type/test/build/benchmark checks.

## Data Layers

- SQLite stores crawl runs, findings, and snapshots.
- `stats.json` stores aggregate and per-seed telemetry.
- `snapshot_diff.json` stores run-to-run change summary and page-level details.
- HTML report contains interactive investigator dashboard views.
