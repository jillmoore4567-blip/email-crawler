# Release Notes - v1.2.0

Release date: 2026-07-09

## Summary

v1.2.0 advances the project from crawler output reporting to investigator-oriented analysis workflows. The release adds richer dashboard analytics, page-level relationship exploration, and stronger release validation while preserving crawler behavior and report output schemas.

## Highlights

- Interactive analytics charts for crawl metrics, email domains, document types, and crawl timing.
- Snapshot comparison panel with page-level change filtering and sorting.
- Page Details panel with extracted artifacts and security-header context.
- Enhanced dashboard usability:
  - global search/filter/sort across findings tables,
  - dark mode,
  - responsive/mobile layout,
  - PNG/SVG chart export.
- Interactive page relationship graph based on existing link graph data:
  - force-directed and hierarchical layouts,
  - zoom and pan,
  - seed/domain/depth/snapshot/link-type filtering,
  - internal vs external link coloring,
  - node click-through to Page Details.

## Performance and Quality

- Dashboard benchmark now includes graph render latency.
- Synthetic dataset benchmark results (1k/5k/10k) remain below the 200 ms threshold for all measured operations.
- Release candidate gates pass:
  - Ruff
  - mypy
  - pytest

## Compatibility Notes

- No crawler engine behavior changes were introduced for this release.
- Existing report output schemas remain compatible (`stats.json`, `snapshot_diff.json`).
- Existing databases continue to migrate in-place through the migration chain.

## Artifacts

- Source: GitHub repository main branch
- Changelog: CHANGELOG.md
- Dashboard docs: docs/GRAPH_VISUALIZATION.md
