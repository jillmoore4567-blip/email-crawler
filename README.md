# Email Extractor & Website Crawler

<!-- markdownlint-disable MD013 -->
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/jillmoore4567-blip/email-crawler/actions/workflows/ci.yml/badge.svg)](https://github.com/jillmoore4567-blip/email-crawler/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/badge/lint-ruff-informational.svg)](https://docs.astral.sh/ruff/)
[![mypy](https://img.shields.io/badge/type%20check-mypy-informational.svg)](https://mypy.readthedocs.io/)
<!-- markdownlint-enable MD013 -->

A modular Python crawler for authorized asset inventory and security
engineering workflows. It supports incremental crawling, historical
snapshots, SQLite persistence, schema migrations, HTML dashboards, and
JSON/CSV exports.

This project is for **authorized asset inventory and defensive testing
only**.

## Why This Project

- Crawl sites with configurable depth, concurrency, retries, and rate limits.
- Extract emails, documents, links, metadata, and optional intelligence signals.
- Persist findings to SQLite with migration-managed schema evolution.
- Compare runs over time with snapshot diffing and historical trend analysis.
- Produce analyst-friendly reports, charts, and machine-readable output files.

## Architecture

```mermaid
flowchart TD
  A[Seed URLs] --> B[Crawl Scheduler]
  B --> C[HTTP Fetcher]
  C --> D[HTML Parser]
  D --> E[Plugin Registry]
  E --> E1[Metadata]
  E --> E2[Email]
  E --> E3[Documents]
  E --> E4[Phones]
  E --> E5[Images]
  E --> E6[JavaScript]
  E --> F[SQLite Storage]
  F --> G[Snapshot History]
  G --> H[HTML Report + JSON + CSV]
```

Extractor registration is defined in
[src/email_crawler/extractors/registry.py](src/email_crawler/extractors/registry.py),
and runtime composition is handled by `build_default_extractors(...)`.

## Installation

```powershell
cd C:\Users\user\email-crawler
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## Quick Start

```powershell
email-crawler --seeds data/seeds.txt --max-pages 100 --max-depth 2 `
  --allow-domain example.com
```

Module mode:

```powershell
python -m email_crawler --seeds data/seeds.txt
```

## Live Monitoring

To generate a standalone live monitor page and stream file:

```powershell
python -m email_crawler `
  --seeds data/seeds.txt `
  --out-live-stream output/crawl_live_stream.jsonl `
  --out-live-monitor-html output/live_monitor.html
```

To host the live monitor with WebSocket and API endpoints during a crawl:

```powershell
python -m email_crawler `
  --seeds data/seeds.txt `
  --serve-live-monitor `
  --live-monitor-host 127.0.0.1 `
  --live-monitor-port 8765
```


The live-monitor API and WebSocket endpoints use bearer authentication
when a token is configured. Send `Authorization: Bearer replace-with-a-secret`
on HTTP requests; WebSocket clients may use the `Authorization` header or
the `?token=replace-with-a-secret` query parameter.

## Configuration

- Defaults are loaded from [config.yaml](config.yaml).
- CLI arguments override YAML defaults.
- Seed input can be plain text or simple CSV (first column URL).

Common options:

- `--seeds`, `--max-pages`, `--max-depth`, `--allow-domain`, `--cross-domain`
- `--resume`, `--incremental`, `--checkpoint-dir`, `--checkpoint-every-pages`
- `--out-stats`, `--out-snapshot-diff`, `--out-sqlite`, `--out-html`
- `--out-live-stream`, `--out-live-monitor-html`, `--serve-live-monitor`
- `--live-monitor-host`, `--live-monitor-port`, `--live-monitor-token`
  --live-monitor-token replace-with-a-secret

## Reports And Outputs

Primary outputs:

- `output/report.html` for the interactive dashboard.
- `output/live_monitor.html` for live crawl monitoring.
- `output/stats.json` for run telemetry and aggregates.
- `output/snapshot_diff.json` for historical run deltas.
- `output/findings.db` for persistent SQLite storage.
- `output/results.json` and `output/results.csv` for downstream automation.

Dashboard highlights include:

- crawl metrics and timing charts
- domain and document-type distributions
- interactive page relationship graph
- global search and detailed page drill-downs
- export options and responsive layout support

## Database And Migrations

Migrations are applied in-order from
[src/email_crawler/migrations](src/email_crawler/migrations):

- `001_initial.sql`
- `002_add_runs.sql`
- `003_page_snapshots.sql`
- `004_provenance_layer.sql`
- `005_snapshot_timeline_indexes.sql`

The migration process is idempotent, preserves legacy data, and tracks
final state in `schema_version`.

Related docs:

- [docs/PROVENANCE_MODEL.md](docs/PROVENANCE_MODEL.md)
- [docs/HISTORICAL_SNAPSHOTS_DESIGN.md](docs/HISTORICAL_SNAPSHOTS_DESIGN.md)

## Testing And CI

```powershell
python -m pip install -e .[dev]
pytest -q
```

CI in [.github/workflows/ci.yml](.github/workflows/ci.yml) runs linting,
type checks, migration tests, packaging checks, benchmark regression checks,
and the full test suite.

## Benchmarks

Generate synthetic benchmark results:

```powershell
python scripts/benchmark_synthetic.py
```

Dashboard performance benchmark:

```powershell
python scripts/benchmark_dashboard.py `
  --output output/benchmarks/dashboard_latest.json
```

Regression check:

```powershell
python scripts/check_benchmark_regression.py `
  --baseline benchmarks/baseline.json `
  --latest output/benchmarks/latest.json
```

## Screenshots

See [docs/screenshots](docs/screenshots):

- [report-overview.png](docs/screenshots/report-overview.png)
- [snapshot-comparison.png](docs/screenshots/snapshot-comparison.png)
- [performance-metrics.png](docs/screenshots/performance-metrics.png)
- [crawl-summary.png](docs/screenshots/crawl-summary.png)

## Contributing

- Open an issue with context and reproducible steps.
- Keep pull requests focused and include tests for behavior changes.
- Run local quality gates before opening a PR:
  - `ruff check src tests`
  - `mypy --config-file mypy.ini`
  - `pytest -q`

## License

MIT License. See [LICENSE](LICENSE).
