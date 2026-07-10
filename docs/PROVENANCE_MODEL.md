# Provenance Model

This document describes Issue #4 provenance tracking introduced for post-v1.2 development.

## Goals

- Stable identifiers for crawl runs, pages, and extracted artifacts.
- Lifecycle visibility with `first_seen` and `last_seen` timestamps.
- Backward-compatible migration for existing SQLite databases.

## Stable Identifiers

- Run: `crawl_runs.run_uid`
  - Backfilled from existing `run_id`.
- Page: `pages.page_uid`
  - Deterministic hash of `seed_url|url`.
  - Stable across runs for the same seed/page pair.
- Artifact: `artifact_provenance.artifact_uid`
  - Deterministic hash of `seed_url|artifact_type|artifact_value`.

## Lifecycle Fields

- Page lifecycle:
  - `pages.first_seen`
  - `pages.last_seen`
- Artifact lifecycle:
  - `artifact_provenance.first_seen`
  - `artifact_provenance.last_seen`
  - `artifact_provenance.last_run_id`

`first_seen` is immutable once established; `last_seen` updates whenever the same page or artifact is observed in later runs.

## Schema Additions

Migration: `src/email_crawler/migrations/004_provenance_layer.sql`

- New table: `artifact_provenance`
- New indexes for provenance lookup patterns
- New indexes for `crawl_runs.run_uid` and `pages.page_uid`

## Backward Compatibility

- Migrations are additive and idempotent.
- Existing tables and CLI/report output formats are preserved.
- Existing databases are backfilled during migration application.

## Query Examples

Most recent lifecycle for a page:

```sql
SELECT page_uid, first_seen, last_seen
FROM pages
WHERE url = ?
ORDER BY last_seen DESC
LIMIT 1;
```

Artifact history state:

```sql
SELECT artifact_type, artifact_value, first_seen, last_seen, last_run_id
FROM artifact_provenance
WHERE artifact_type = 'email';
```
