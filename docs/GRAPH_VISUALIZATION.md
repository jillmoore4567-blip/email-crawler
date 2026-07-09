# Graph Visualization (v1.2)

The dashboard includes an interactive page relationship graph built from existing crawl report data.

## Data Source Constraints

- Uses existing `page_findings` link data already present in reporting payload generation.
- Does not modify crawler engine behavior.
- Does not alter output report schemas (`stats.json`, `snapshot_diff.json`).

## Graph Capabilities

- Force-directed layout for exploratory relationship mapping.
- Hierarchical layout for depth-oriented traversal views.
- Zoom and pan in both layouts.
- Node selection opens the existing Page Details panel.
- Domain and depth filtering controls.
- Snapshot change highlighting (`new`, `changed`, `removed`, unchanged).
- Internal links and external links are rendered with distinct edge colors.

## Rendering Notes

- Node size is weighted by link degree and extracted artifact counts.
- Node depth is computed from shortest seed-to-page path when available.
- Graph coordinates are precomputed in payload generation for fast browser rendering.

## Validation

- Integration tests assert graph controls and interactive wiring in generated HTML.
- Dashboard benchmark includes graph render latency in threshold checks.
