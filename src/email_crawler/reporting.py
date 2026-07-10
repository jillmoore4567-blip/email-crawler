from __future__ import annotations

import json
from collections import Counter, deque
from datetime import datetime, timezone
from html import escape
from math import cos, pi, sin
from pathlib import Path
from urllib.parse import urlsplit

from .crawler import CrawlResult


SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]
SEVERITY_WEIGHTS = {
  "info": 2,
  "low": 8,
  "medium": 18,
  "high": 35,
  "critical": 55,
}


def _severity_rank(level: str) -> int:
  try:
    return SEVERITY_ORDER.index(level)
  except ValueError:
    return 0


def _infer_severity(finding_type: str, details_text: str = "") -> str:
  token = f"{finding_type} {details_text}".lower()

  if any(item in token for item in ("api_key", "secret", "token", "credential", "password")):
    return "critical"
  if any(item in token for item in ("admin", "exposed", "directory_listing", "backup")):
    return "high"
  if any(item in token for item in ("metadata", "broken_link", "broken", "document", "pdf")):
    return "medium"
  if any(item in token for item in ("email", "phone", "contact")):
    return "low"
  if any(item in token for item in ("security.txt", "robots.txt", "sitemap")):
    return "info"
  return "low"


def _compute_risk_summary(rows: list[dict], pages_crawled: int) -> dict:
  counts = {level: 0 for level in SEVERITY_ORDER}
  for row in rows:
    sev = str(row.get("severity") or "low").lower()
    if sev not in counts:
      sev = "low"
    counts[sev] += 1

  weighted = sum(counts[level] * SEVERITY_WEIGHTS[level] for level in SEVERITY_ORDER)
  capacity = max(1, pages_crawled) * SEVERITY_WEIGHTS["critical"]
  score = min(100, round((weighted / capacity) * 100))

  if score >= 70:
    exposure = "CRITICAL"
  elif score >= 50:
    exposure = "HIGH"
  elif score >= 25:
    exposure = "MEDIUM"
  else:
    exposure = "LOW"

  return {
    "score": score,
    "exposure": exposure,
    "counts": counts,
    "weighted": weighted,
  }


def write_html_report(
  results: list[CrawlResult],
  stats: dict,
  output_path: str,
  *,
  live_stream_path: str = "",
  live_monitor_token: str = "",
) -> None:
  payload = _build_dashboard_payload(
    results,
    stats,
    live_stream_path=live_stream_path,
    live_monitor_token=live_monitor_token,
  )
  if live_stream_path:
    report_dir = Path(output_path).parent.resolve()
    stream_path = Path(live_stream_path).resolve()
    try:
      relative = stream_path.relative_to(report_dir)
      payload["live_stream"]["path"] = relative.as_posix()
    except ValueError:
      payload["live_stream"]["path"] = stream_path.as_posix()

    html = f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>OSINT Crawl Dashboard</title>
  <script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script>
  <style>
    :root {{
      --bg:#f4f7fb;
      --ink:#1f2937;
      --muted:#6b7280;
      --card:#ffffff;
      --line:#dbe3ee;
      --accent:#0f766e;
      --accent2:#1d4ed8;
      --accent3:#b45309;
      --header-ink:#0b2447;
      --header-bg:#f7fafd;
      --focus:#93c5fd;
      --panel-shadow:0 4px 18px rgba(31,41,55,.06);
    }}
    [data-theme='dark'] {{
      --bg:#0b1220;
      --ink:#e2e8f0;
      --muted:#94a3b8;
      --card:#111a2b;
      --line:#24324a;
      --accent:#0d9488;
      --accent2:#2563eb;
      --accent3:#f59e0b;
      --header-ink:#dbeafe;
      --header-bg:#0f172a;
      --focus:#38bdf8;
      --panel-shadow:0 8px 24px rgba(0,0,0,.4);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; color:var(--ink); background:radial-gradient(1200px 600px at -10% -20%, #e7f6f2 0%, transparent 60%), var(--bg); font-family:'Segoe UI', Tahoma, sans-serif; }}
    .wrap {{ max-width:1300px; margin:20px auto; padding:0 14px 30px; }}
    .top {{ background:linear-gradient(120deg,#0f766e,#1d4ed8); color:#fff; border-radius:16px; padding:18px; box-shadow:0 10px 30px rgba(15,118,110,.28); }}
    .top h1 {{ margin:0 0 4px; font-size:28px; }}
    .sub {{ opacity:.9; font-size:14px; }}
    .kpi {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin-top:14px; }}
    .kpi .box {{ background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25); border-radius:10px; padding:10px; }}
    .kpi .box b {{ display:block; font-size:22px; margin-top:4px; }}
    .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px; }}
    .grid3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:10px; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:12px; box-shadow:var(--panel-shadow); }}
    .card h2 {{ margin:0 0 8px; font-size:17px; }}
    .plot {{ width:100%; height:340px; }}
    .plotTall {{ width:100%; height:420px; }}
    .toolbar {{ margin:6px 0 8px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
    button {{ border:1px solid var(--line); background:var(--card); color:var(--ink); border-radius:8px; padding:6px 10px; cursor:pointer; }}
    button:hover {{ border-color:#b8c6da; background:color-mix(in srgb, var(--card) 92%, #ffffff 8%); }}
    label {{ font-size:12px; color:var(--muted); display:block; margin-bottom:4px; }}
    select,input {{ width:100%; border:1px solid var(--line); border-radius:8px; padding:8px; background:var(--card); color:var(--ink); }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ border-bottom:1px solid var(--line); padding:7px 6px; text-align:left; vertical-align:top; }}
    th {{ color:var(--header-ink); background:var(--header-bg); position:sticky; top:0; }}
    .scroll {{ max-height:320px; overflow:auto; border:1px solid var(--line); border-radius:10px; }}
    .pill {{ display:inline-block; margin:2px 4px 2px 0; padding:2px 7px; border:1px solid var(--line); border-radius:999px; font-size:12px; background:#f8fafc; }}
    .mono {{ font-family:Consolas, 'Courier New', monospace; font-size:12px; color:var(--muted); }}
    .clickable {{ cursor:pointer; user-select:none; }}
    .clickable::after {{ content:' ↕'; font-size:11px; color:#64748b; }}
    tr[tabindex='0']:focus {{ outline:2px solid var(--focus); outline-offset:-2px; }}
    .type-filters {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .type-filters label {{ display:flex; align-items:center; gap:6px; margin:0; border:1px solid var(--line); border-radius:999px; padding:5px 8px; background:var(--card); }}
    .type-filters input {{ width:auto; }}
    .details-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:8px; }}
    .details-grid .card h3 {{ margin:0 0 6px; font-size:14px; }}
    .top-actions {{ margin-top:10px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
    .top-actions .spacer {{ flex:1 1 auto; }}
    .segment {{ display:flex; align-items:center; gap:8px; }}
    .graph-controls {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:8px; margin-bottom:8px; }}
    .graph-legend {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:8px; }}
    .dot {{ display:inline-block; width:10px; height:10px; border-radius:999px; margin-right:5px; }}
    .dot-same {{ background:#94a3b8; }}
    .dot-new {{ background:#16a34a; }}
    .dot-changed {{ background:#f59e0b; }}
    .dot-removed {{ background:#dc2626; }}
    .monitor-grid {{ display:grid; grid-template-columns:2fr 1fr; gap:12px; }}
    .monitor-track {{ height:12px; border-radius:999px; background:color-mix(in srgb, var(--line) 78%, transparent); overflow:hidden; border:1px solid var(--line); }}
    .monitor-fill {{ height:100%; background:linear-gradient(90deg,#0ea5e9,#16a34a); width:0%; transition:width .45s ease; }}
    .monitor-metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:8px; margin-top:10px; }}
    .monitor-metrics .tile {{ border:1px solid var(--line); border-radius:10px; padding:8px; background:color-mix(in srgb, var(--card) 94%, #ffffff 6%); }}
    .monitor-metrics .tile b {{ font-size:18px; display:block; margin-top:2px; }}
    .feed {{ max-height:220px; overflow:auto; border:1px solid var(--line); border-radius:10px; padding:8px; background:color-mix(in srgb, var(--card) 96%, #ffffff 4%); }}
    .feed-item {{ display:flex; gap:8px; align-items:flex-start; margin-bottom:7px; }}
    .feed-item .time {{ color:var(--muted); min-width:74px; font-family:Consolas, 'Courier New', monospace; font-size:12px; }}
    .risk-wrap {{ border:1px solid var(--line); border-radius:12px; padding:10px; }}
    .risk-track {{ height:14px; border-radius:999px; overflow:hidden; background:color-mix(in srgb, var(--line) 80%, transparent); border:1px solid var(--line); }}
    .risk-fill {{ height:100%; width:0%; transition:width .5s ease; background:linear-gradient(90deg,#22c55e 0%, #eab308 50%, #ef4444 100%); }}
    .sev-badges {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }}
    .sev-badge {{ border:1px solid var(--line); border-radius:999px; padding:4px 8px; font-size:12px; }}
    .sev-info {{ background:#e0f2fe; color:#0c4a6e; }}
    .sev-low {{ background:#dcfce7; color:#14532d; }}
    .sev-medium {{ background:#fef9c3; color:#854d0e; }}
    .sev-high {{ background:#ffedd5; color:#9a3412; }}
    .sev-critical {{ background:#fee2e2; color:#991b1b; }}
    .group-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:10px; }}
    .group-list {{ max-height:220px; overflow:auto; border:1px solid var(--line); border-radius:10px; padding:8px; }}
    .group-list ul {{ margin:0; padding-left:16px; }}
    .group-list li {{ margin:3px 0; }}
    .shot-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:10px; }}
    .shot {{ border:1px solid var(--line); border-radius:10px; overflow:hidden; background:color-mix(in srgb, var(--card) 95%, #ffffff 5%); }}
    .shot img {{ width:100%; height:140px; object-fit:cover; display:block; background:#0f172a; }}
    .shot .meta {{ padding:8px; font-size:12px; }}
    .det-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:10px; }}
    .det-card {{ border:1px solid var(--line); border-radius:10px; padding:10px; }}
    .det-card h3 {{ margin:0 0 6px; font-size:14px; }}
    .det-status {{ display:inline-block; border-radius:999px; padding:2px 8px; font-size:11px; }}
    .det-ok {{ background:#dcfce7; color:#14532d; }}
    .det-info {{ background:#e0f2fe; color:#0c4a6e; }}
    .det-low {{ background:#fef9c3; color:#854d0e; }}
    .det-medium {{ background:#ffedd5; color:#9a3412; }}
    .det-high {{ background:#fee2e2; color:#991b1b; }}
    @media (max-width: 950px) {{ .grid2 {{ grid-template-columns:1fr; }} .grid3 {{ grid-template-columns:1fr; }} }}
    @media (max-width: 950px) {{ .monitor-grid {{ grid-template-columns:1fr; }} }}
    @media (max-width: 640px) {{
      .wrap {{ margin:12px auto; padding:0 8px 20px; }}
      .top h1 {{ font-size:22px; }}
      .plot {{ height:300px; }}
      .plotTall {{ height:360px; }}
      .toolbar {{ gap:6px; }}
      button {{ padding:6px 8px; font-size:12px; }}
    }}
  </style>
</head>
<body>
  <div class='wrap'>
    <section class='top'>
      <h1>OSINT Crawl Dashboard</h1>
      <div class='sub'>Generated {escape(payload['generated_at'])} | Authorized asset discovery summary</div>
      <div class='top-actions'>
        <div class='segment'>
          <label for='chartExportFormat' style='margin:0;'>Chart Export</label>
          <select id='chartExportFormat' style='width:auto;'>
            <option value='png'>PNG</option>
            <option value='svg'>SVG</option>
          </select>
        </div>
        <div class='spacer'></div>
        <button type='button' onclick='exportPdfReport()'>Export PDF</button>
        <button type='button' onclick='exportMarkdownReport()'>Export Markdown</button>
        <button id='themeToggle' type='button' onclick='toggleTheme()' aria-label='Toggle dark mode'>Dark Mode</button>
      </div>
      <div class='kpi'>
        <div class='box'><span>Seeds</span><b>{payload['stats'].get('seeds_processed', 0)}</b></div>
        <div class='box'><span>Pages</span><b>{payload['stats'].get('pages_crawled', 0)}</b></div>
        <div class='box'><span>Emails</span><b>{payload['stats'].get('unique_emails', 0)}</b></div>
        <div class='box'><span>Documents</span><b>{payload['stats'].get('unique_documents', 0)}</b></div>
        <div class='box'><span>Domains</span><b>{payload['derived']['unique_domains']}</b></div>
        <div class='box'><span>Intelligence</span><b>{payload['stats'].get('intelligence_findings', 0)}</b></div>
        <div class='box'><span>Errors</span><b>{payload['stats'].get('errors', 0)}</b></div>
      </div>
    </section>

    <section class='grid2'>
      <div class='card'>
        <h2>Executive Summary</h2>
        <div class='mono'>Target scope: authorized OSINT and asset discovery only.</div>
        <div class='monitor-metrics' style='margin-top:10px;'>
          <div class='tile'><span>Pages Crawled</span><b>{payload['stats'].get('pages_crawled', 0)}</b></div>
          <div class='tile'><span>Assets Found</span><b>{payload['derived'].get('assets_total', 0)}</b></div>
          <div class='tile'><span>Documents</span><b>{payload['stats'].get('unique_documents', 0)}</b></div>
          <div class='tile'><span>Images</span><b>{payload['derived'].get('unique_images', 0)}</b></div>
          <div class='tile'><span>Emails</span><b>{payload['stats'].get('unique_emails', 0)}</b></div>
          <div class='tile'><span>Phone Numbers</span><b>{payload['derived'].get('unique_phones', 0)}</b></div>
          <div class='tile'><span>Domains</span><b>{payload['derived'].get('unique_domains', 0)}</b></div>
          <div class='tile'><span>Overall Exposure</span><b>{escape(str(payload['risk'].get('exposure', 'LOW')))}</b></div>
        </div>
      </div>
      <div class='card'>
        <h2>Overall Risk</h2>
        <div class='risk-wrap'>
          <div class='mono'>Risk score: <b id='riskScoreText'>{escape(str(payload['risk'].get('score', 0)))}%</b></div>
          <div class='risk-track' style='margin-top:8px;'><div id='riskFill' class='risk-fill'></div></div>
          <div class='sev-badges'>
            <span class='sev-badge sev-info'>INFO: {escape(str(payload['risk'].get('counts', {}).get('info', 0)))}</span>
            <span class='sev-badge sev-low'>LOW: {escape(str(payload['risk'].get('counts', {}).get('low', 0)))}</span>
            <span class='sev-badge sev-medium'>MEDIUM: {escape(str(payload['risk'].get('counts', {}).get('medium', 0)))}</span>
            <span class='sev-badge sev-high'>HIGH: {escape(str(payload['risk'].get('counts', {}).get('high', 0)))}</span>
            <span class='sev-badge sev-critical'>CRITICAL: {escape(str(payload['risk'].get('counts', {}).get('critical', 0)))}</span>
          </div>
        </div>
      </div>
    </section>

    <section class='card'>
      <h2>Real-Time Crawl Monitor (Playback)</h2>
      <div class='monitor-grid'>
        <div>
          <div class='mono' id='monitorCurrentUrl'>Current URL: waiting for timeline data...</div>
          <div class='monitor-track' style='margin-top:8px;'><div id='monitorProgress' class='monitor-fill'></div></div>
          <div class='monitor-metrics'>
            <div class='tile'><span>Progress</span><b id='monitorProgressText'>0%</b></div>
            <div class='tile'><span>Pages Crawled</span><b id='monitorPages'>0</b></div>
            <div class='tile'><span>Requests/sec</span><b id='monitorRps'>0.00</b></div>
            <div class='tile'><span>Queue Size</span><b id='monitorQueue'>0</b></div>
            <div class='tile'><span>Depth</span><b id='monitorDepth'>0</b></div>
            <div class='tile'><span>ETA</span><b id='monitorEta'>n/a</b></div>
          </div>
        </div>
        <div>
          <div class='mono' style='margin-bottom:6px;'>Timeline Events</div>
          <div id='timelineFeed' class='feed'></div>
        </div>
      </div>
    </section>

    <section class='card'>
      <h2>Interactive Intelligence Dashboard</h2>
      <div class='toolbar'>
        <input id='intelGroupSearch' type='text' placeholder='Search grouped findings...' oninput='renderGroupedFindings()'/>
      </div>
      <div id='intelGroups' class='group-grid'></div>
    </section>

    <section class='card'>
      <h2>Detection Modules</h2>
      <div id='detectionModules' class='det-grid'></div>
    </section>

    <section class='card'>
      <h2>Screenshot Capture</h2>
      <div id='screenshotGallery' class='shot-grid'></div>
    </section>

    <section class='grid2'>
      <div class='card'>
        <h2>Technology Fingerprinting</h2>
        <div id='technologyList' class='group-list'></div>
      </div>
      <div class='card'>
        <h2>Detected Technologies (Top)</h2>
        <div class='toolbar'><button onclick="exportChart('technologyPlot','technology_fingerprints')">Export Chart</button></div>
        <div id='technologyPlot' class='plot'></div>
      </div>
    </section>

    <section class='card'>
      <h2>Snapshot Comparison</h2>
      {_render_snapshot_comparison(payload['snapshot'])}
    </section>

    <section class='card'>
      <h2>Performance Observability</h2>
      {_render_performance_summary(payload['performance'])}
      <div class='toolbar'><button onclick="exportChart('performancePlot','performance_per_seed')">Export Chart</button></div>
      <div id='performancePlot' class='plot'></div>
    </section>

    <section class='card'>
      <h2>Dashboard Filters</h2>
      <div class='grid3'>
        <div>
          <label for='globalSearch'>Global Search</label>
          <input id='globalSearch' type='text' placeholder='Search pages, assets, findings, URLs, details...'/>
        </div>
        <div>
          <label for='seedFilter'>Seed</label>
          <select id='seedFilter'></select>
        </div>
        <div>
          <label for='domainFilter'>Domain</label>
          <select id='domainFilter'></select>
        </div>
        <div>
          <label for='findingTypeFilter'>Finding Type</label>
          <select id='findingTypeFilter'></select>
        </div>
        <div>
          <label for='fromDate'>From Date</label>
          <input id='fromDate' type='date'/>
        </div>
        <div>
          <label for='toDate'>To Date</label>
          <input id='toDate' type='date'/>
        </div>
        <div class='toolbar' style='align-self:end;'>
          <button onclick='applyFilters()'>Apply Filters</button>
          <button onclick='resetFilters()'>Reset</button>
        </div>
      </div>
      <div style='margin-top:10px;'>
        <label>Type Filters</label>
        <div id='typeFilterChecks' class='type-filters'></div>
      </div>
    </section>

    <section class='grid2'>
      <div class='card'>
        <h2>Crawl Metrics</h2>
        <div class='toolbar'><button onclick="exportChart('crawlMetricsPlot','crawl_metrics')">Export Chart</button></div>
        <div id='crawlMetricsPlot' class='plot'></div>
      </div>
      <div class='card'>
        <h2>Email Domain Distribution</h2>
        <div class='toolbar'><button onclick="exportChart('emailDomainPlot','email_domain_distribution')">Export Chart</button></div>
        <div id='emailDomainPlot' class='plot'></div>
      </div>
    </section>

    <section class='grid2'>
      <div class='card'>
        <h2>Document Type Distribution</h2>
        <div class='toolbar'><button onclick="exportChart('documentTypePlot','document_type_distribution')">Export Chart</button></div>
        <div id='documentTypePlot' class='plot'></div>
      </div>
      <div class='card'>
        <h2>Crawl Timing</h2>
        <div class='toolbar'><button onclick="exportChart('crawlTimingPlot','crawl_timing')">Export Chart</button></div>
        <div id='crawlTimingPlot' class='plot'></div>
      </div>
    </section>

    <section class='card'>
      <h2>Crawl Timeline</h2>
      <div class='toolbar'><button onclick="exportChart('timelinePlot','crawl_timeline')">Export Chart</button></div>
      <div id='timelinePlot' class='plot'></div>
    </section>

    <section class='card'>
      <h2>Page Relationship Graph</h2>
      <div class='graph-controls'>
        <div>
          <label for='graphLayoutMode'>Layout</label>
          <select id='graphLayoutMode' onchange='applyGraphFilters()'>
            <option value='force'>Force-Directed</option>
            <option value='hierarchical'>Hierarchical</option>
          </select>
        </div>
        <div>
          <label for='graphSeedFilter'>Graph Seed</label>
          <select id='graphSeedFilter' onchange='applyGraphFilters()'></select>
        </div>
        <div>
          <label for='graphDomainFilter'>Graph Domain</label>
          <select id='graphDomainFilter' onchange='applyGraphFilters()'></select>
        </div>
        <div>
          <label for='graphDepthFilter'>Depth</label>
          <select id='graphDepthFilter' onchange='applyGraphFilters()'>
            <option value='all'>All</option>
          </select>
        </div>
        <div>
          <label for='graphLinkTypeFilter'>Link Type</label>
          <select id='graphLinkTypeFilter' onchange='applyGraphFilters()'>
            <option value='all'>All</option>
            <option value='internal'>Internal</option>
            <option value='external'>External</option>
          </select>
        </div>
        <div>
          <label for='graphSnapshotFilter'>Snapshot Highlight</label>
          <select id='graphSnapshotFilter' onchange='applyGraphFilters()'>
            <option value='all'>All</option>
            <option value='new'>New Only</option>
            <option value='changed'>Changed Only</option>
            <option value='removed'>Removed Only</option>
          </select>
        </div>
        <div>
          <label for='graphNodeLimit'>Node Limit</label>
          <select id='graphNodeLimit' onchange='applyGraphFilters()'>
            <option value='80'>80</option>
            <option value='120' selected>120</option>
            <option value='180'>180</option>
            <option value='240'>240</option>
          </select>
        </div>
        <div>
          <label for='graphSearch'>Graph Search</label>
          <input id='graphSearch' type='text' placeholder='Filter by URL or domain' oninput='applyGraphFilters()'/>
        </div>
      </div>
      <div class='toolbar'>
        <button onclick="exportChart('pageGraphPlot','page_relationship_graph')">Export Chart</button>
        <span id='pageGraphCount' class='mono'></span>
      </div>
      <div id='pageGraphPlot' class='plotTall'></div>
      <div class='graph-legend mono'>
        <span><span class='dot dot-same'></span>Unchanged</span>
        <span><span class='dot dot-new'></span>New</span>
        <span><span class='dot dot-changed'></span>Changed</span>
        <span><span class='dot dot-removed'></span>Removed</span>
        <span><span class='dot' style='background:#0ea5e9;'></span>Internal Link</span>
        <span><span class='dot' style='background:#ef4444;'></span>External Link</span>
      </div>
      <div class='mono'>Supports force-directed and hierarchical layouts. Zoom with mouse wheel, pan by dragging, and click a node to open Page Details.</div>
    </section>

    <section class='card'>
      <h2>Crawl Graph (Domain Flow)</h2>
      <div class='toolbar'><button onclick="exportChart('graphPlot','crawl_graph')">Export Chart</button></div>
      <div id='graphPlot' class='plotTall'></div>
      <div class='mono'>Sankey edges are aggregated from discovered source-domain -> target-domain links.</div>
    </section>

    <section class='grid2'>
      <div id='pages-table' class='card'>
        <h2>Pages Table</h2>
        <div class='toolbar'>
          <button onclick="exportRows(filteredPageRows, 'pages_filtered', 'csv')">Export CSV</button>
          <button onclick="exportRows(filteredPageRows, 'pages_filtered', 'json')">Export JSON</button>
          <span id='pagesCount' class='mono'></span>
        </div>
        <div class='scroll'>
          <table>
            <thead>
              <tr>
                <th class='clickable' onclick="sortTable('pages','seed','text')">Seed</th>
                <th class='clickable' onclick="sortTable('pages','domain','text')">Domain</th>
                <th class='clickable' onclick="sortTable('pages','title','text')">Title</th>
                <th class='clickable' onclick="sortTable('pages','status','number')">Status</th>
                <th class='clickable' onclick="sortTable('pages','emails_count','number')">Emails</th>
                <th class='clickable' onclick="sortTable('pages','documents_count','number')">Documents</th>
                <th class='clickable' onclick="sortTable('pages','timestamp','date')">Timestamp</th>
              </tr>
            </thead>
            <tbody id='pagesTbody'></tbody>
          </table>
        </div>
      </div>

      <div id='emails-table' class='card'>
        <h2>Emails Table</h2>
        <div class='toolbar'>
          <button onclick="exportRows(filteredEmailRows, 'emails_filtered', 'csv')">Export CSV</button>
          <button onclick="exportRows(filteredEmailRows, 'emails_filtered', 'json')">Export JSON</button>
          <span id='emailsCount' class='mono'></span>
        </div>
        <div class='scroll'>
          <table>
            <thead><tr><th class='clickable' onclick="sortTable('emails','seed','text')">Seed</th><th class='clickable' onclick="sortTable('emails','domain','text')">Domain</th><th class='clickable' onclick="sortTable('emails','value','text')">Email</th><th>Page URL</th><th class='clickable' onclick="sortTable('emails','timestamp','date')">Timestamp</th></tr></thead>
            <tbody id='emailsTbody'></tbody>
          </table>
        </div>
      </div>
    </section>

    <section class='grid2'>
      <div id='documents-table' class='card'>
        <h2>Documents Table</h2>
        <div class='toolbar'>
          <button onclick="exportRows(filteredDocumentRows, 'documents_filtered', 'csv')">Export CSV</button>
          <button onclick="exportRows(filteredDocumentRows, 'documents_filtered', 'json')">Export JSON</button>
          <span id='documentsCount' class='mono'></span>
        </div>
        <div class='scroll'>
          <table>
            <thead><tr><th class='clickable' onclick="sortTable('documents','seed','text')">Seed</th><th class='clickable' onclick="sortTable('documents','domain','text')">Domain</th><th class='clickable' onclick="sortTable('documents','value','text')">Document</th><th>Page URL</th><th class='clickable' onclick="sortTable('documents','timestamp','date')">Timestamp</th></tr></thead>
            <tbody id='documentsTbody'></tbody>
          </table>
        </div>
      </div>

      <div id='intel-table' class='card'>
        <h2>Findings Table</h2>
        <div class='toolbar'>
          <button onclick="exportRows(filteredIntelRows, 'intelligence_filtered', 'csv')">Export CSV</button>
          <button onclick="exportRows(filteredIntelRows, 'intelligence_filtered', 'json')">Export JSON</button>
          <span id='intelCount' class='mono'></span>
        </div>
        <div class='scroll'>
          <table>
            <thead><tr><th class='clickable' onclick="sortTable('intel','seed','text')">Seed</th><th class='clickable' onclick="sortTable('intel','domain','text')">Domain</th><th class='clickable' onclick="sortTable('intel','type','text')">Type</th><th class='clickable' onclick="sortTable('intel','severity','text')">Severity</th><th>URL</th><th class='clickable' onclick="sortTable('intel','status','text')">Status</th><th class='clickable' onclick="sortTable('intel','timestamp','date')">Timestamp</th><th>Details</th></tr></thead>
            <tbody id='intelTbody'></tbody>
          </table>
        </div>
      </div>
    </section>

    <section class='card'>
      <h2>Page Details</h2>
      <div id='pageDetailsPanel' class='mono'>Select a page in any table to inspect extracted artifacts.</div>
    </section>

    <section class='card'>
      <h2>Crawl Errors</h2>
      <div class='scroll'>
        <table>
          <thead><tr><th>Seed</th><th>Error</th></tr></thead>
          <tbody>{_render_error_rows(payload['errors'])}</tbody>
        </table>
      </div>
    </section>
  </div>

  <script>
    const payload = {json.dumps(payload, ensure_ascii=True)};
    const FILTER_STATE_KEY = 'osint_dashboard_filters_v1';
    const THEME_STATE_KEY = 'osint_dashboard_theme_v1';

    let filteredPageRows = [...payload.tables.page_rows];
    let filteredEmailRows = [...payload.tables.email_rows];
    let filteredDocumentRows = [...payload.tables.document_rows];
    let filteredIntelRows = [...payload.tables.intelligence_rows];
    let selectedPageUrl = '';
    let snapshotRows = [...(payload.snapshot.page_changes || [])];
    let filteredSnapshotRows = [...snapshotRows];
    const snapshotChangeByUrl = Object.fromEntries(snapshotRows.map(item => [String(item.url || ''), String(item.change_type || 'unchanged')]));
    const tableSortState = {{
      pages: {{key: 'timestamp', dir: 'desc', type: 'date'}},
      emails: {{key: 'timestamp', dir: 'desc', type: 'date'}},
      documents: {{key: 'timestamp', dir: 'desc', type: 'date'}},
      intel: {{key: 'timestamp', dir: 'desc', type: 'date'}},
    }};

    function currentExportFormat() {{
      const el = document.getElementById('chartExportFormat');
      return el ? (el.value || 'png') : 'png';
    }}

    function exportChart(divId, filename) {{
      const format = currentExportFormat();
      const width = format === 'svg' ? 1400 : 1200;
      const height = 700;
      Plotly.downloadImage(divId, {{format, filename, width, height, scale:2}});
    }}

    function applyTheme(theme) {{
      document.documentElement.setAttribute('data-theme', theme);
      const btn = document.getElementById('themeToggle');
      if (btn) btn.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
      localStorage.setItem(THEME_STATE_KEY, theme);
    }}

    function toggleTheme() {{
      const current = document.documentElement.getAttribute('data-theme') || 'light';
      applyTheme(current === 'dark' ? 'light' : 'dark');
    }}

    function populateFilters() {{
      fillSelect('seedFilter', payload.filters.seeds);
      fillSelect('domainFilter', payload.filters.domains);
      fillSelect('findingTypeFilter', payload.filters.finding_types);
      fillSelect('graphSeedFilter', payload.filters.seeds);
      fillSelect('graphDomainFilter', payload.filters.domains);
      fillDepthSelect(payload.charts.page_graph?.depth_values || []);
      renderTypeFilters(payload.filters.finding_types || []);

      const search = document.getElementById('globalSearch');
      search.addEventListener('input', applyFilters);
      search.addEventListener('keydown', (event) => {{
        if (event.key === 'Escape') {{
          search.value = '';
          applyFilters();
        }}
      }});

      document.addEventListener('keydown', (event) => {{
        if (event.key === '/' && document.activeElement !== search) {{
          event.preventDefault();
          search.focus();
        }}
      }});

      loadFilterState();
      applyGraphFilters();
    }}

    function fillDepthSelect(depthValues) {{
      const el = document.getElementById('graphDepthFilter');
      if (!el) return;
      const opts = ['<option value="all">All</option>'];
      for (const depth of depthValues) {{
        opts.push(`<option value="${{escapeHtml(String(depth))}}">Depth ${{escapeHtml(String(depth))}}</option>`);
      }}
      el.innerHTML = opts.join('');
    }}

    function fillSelect(id, options) {{
      const el = document.getElementById(id);
      const merged = ['All', ...options];
      el.innerHTML = merged.map(v => `<option value="${{escapeHtml(v)}}">${{escapeHtml(v)}}</option>`).join('');
    }}

    function renderTypeFilters(types) {{
      const root = document.getElementById('typeFilterChecks');
      root.innerHTML = types.map(type => `
        <label>
          <input type="checkbox" class="type-filter" value="${{escapeHtml(type)}}" checked onchange="applyFilters()"/>
          <span>${{escapeHtml(type)}}</span>
        </label>
      `).join('');
    }}

    function activeTypeSet() {{
      const boxes = Array.from(document.querySelectorAll('.type-filter'));
      const enabled = boxes.filter(box => box.checked).map(box => box.value);
      return new Set(enabled);
    }}

    function saveFilterState() {{
      const boxes = Array.from(document.querySelectorAll('.type-filter'));
      const state = {{
        seed: document.getElementById('seedFilter').value,
        domain: document.getElementById('domainFilter').value,
        findingType: document.getElementById('findingTypeFilter').value,
        fromDate: document.getElementById('fromDate').value,
        toDate: document.getElementById('toDate').value,
        search: document.getElementById('globalSearch').value,
        selectedTypes: boxes.filter(box => box.checked).map(box => box.value),
        selectedPageUrl,
        graphSeed: document.getElementById('graphSeedFilter')?.value || 'All',
        graphDomain: document.getElementById('graphDomainFilter')?.value || 'All',
        graphDepth: document.getElementById('graphDepthFilter')?.value || 'all',
        graphLayoutMode: document.getElementById('graphLayoutMode')?.value || 'force',
        graphLinkType: document.getElementById('graphLinkTypeFilter')?.value || 'all',
        graphSnapshot: document.getElementById('graphSnapshotFilter')?.value || 'all',
        graphSearch: document.getElementById('graphSearch')?.value || '',
        graphNodeLimit: document.getElementById('graphNodeLimit')?.value || '120',
      }};
      localStorage.setItem(FILTER_STATE_KEY, JSON.stringify(state));
    }}

    function loadFilterState() {{
      const raw = localStorage.getItem(FILTER_STATE_KEY);
      if (!raw) return;
      try {{
        const state = JSON.parse(raw);
        if (state.seed) document.getElementById('seedFilter').value = state.seed;
        if (state.domain) document.getElementById('domainFilter').value = state.domain;
        if (state.findingType) document.getElementById('findingTypeFilter').value = state.findingType;
        if (state.fromDate) document.getElementById('fromDate').value = state.fromDate;
        if (state.toDate) document.getElementById('toDate').value = state.toDate;
        if (state.search) document.getElementById('globalSearch').value = state.search;
        if (state.graphSeed) document.getElementById('graphSeedFilter').value = state.graphSeed;
        if (state.graphDomain) document.getElementById('graphDomainFilter').value = state.graphDomain;
        if (state.graphDepth) document.getElementById('graphDepthFilter').value = state.graphDepth;
        if (state.graphLayoutMode) document.getElementById('graphLayoutMode').value = state.graphLayoutMode;
        if (state.graphLinkType) document.getElementById('graphLinkTypeFilter').value = state.graphLinkType;
        if (state.graphSnapshot) document.getElementById('graphSnapshotFilter').value = state.graphSnapshot;
        if (state.graphSearch) document.getElementById('graphSearch').value = state.graphSearch;
        if (state.graphNodeLimit) document.getElementById('graphNodeLimit').value = state.graphNodeLimit;
        if (Array.isArray(state.selectedTypes)) {{
          const allowed = new Set(state.selectedTypes);
          Array.from(document.querySelectorAll('.type-filter')).forEach(box => {{
            box.checked = allowed.has(box.value);
          }});
        }}
        if (state.selectedPageUrl) selectedPageUrl = state.selectedPageUrl;
      }} catch (_err) {{
        // Ignore invalid persisted state.
      }}
    }}

    function parseDateOnly(ts) {{
      if (!ts) return null;
      const d = new Date(ts);
      if (Number.isNaN(d.getTime())) return null;
      return new Date(d.getFullYear(), d.getMonth(), d.getDate());
    }}

    function withinDate(ts, fromDate, toDate) {{
      if (!fromDate && !toDate) return true;
      const d = parseDateOnly(ts);
      if (!d) return false;
      if (fromDate) {{
        const from = new Date(fromDate + 'T00:00:00');
        if (d < from) return false;
      }}
      if (toDate) {{
        const to = new Date(toDate + 'T00:00:00');
        if (d > to) return false;
      }}
      return true;
    }}

    function applyFilters() {{
      const seed = document.getElementById('seedFilter').value;
      const domain = document.getElementById('domainFilter').value;
      const findingType = document.getElementById('findingTypeFilter').value;
      const fromDate = document.getElementById('fromDate').value;
      const toDate = document.getElementById('toDate').value;
      const query = (document.getElementById('globalSearch').value || '').trim().toLowerCase();
      const enabledTypes = activeTypeSet();

      filteredPageRows = payload.tables.page_rows.filter(row => {{
        if (seed !== 'All' && row.seed !== seed) return false;
        if (domain !== 'All' && row.domain !== domain) return false;
        if (findingType !== 'All' && !(row.finding_types || []).includes(findingType)) return false;
        if (enabledTypes.size > 0 && !(row.finding_types || []).some(t => enabledTypes.has(t))) return false;
        return withinDate(row.timestamp, fromDate, toDate);
      }});

      filteredEmailRows = payload.tables.email_rows.filter(row => {{
        if (seed !== 'All' && row.seed !== seed) return false;
        if (domain !== 'All' && row.domain !== domain) return false;
        if (findingType !== 'All' && findingType !== 'email') return false;
        if (enabledTypes.size > 0 && !enabledTypes.has('email')) return false;
        return withinDate(row.timestamp, fromDate, toDate);
      }});

      filteredDocumentRows = payload.tables.document_rows.filter(row => {{
        if (seed !== 'All' && row.seed !== seed) return false;
        if (domain !== 'All' && row.domain !== domain) return false;
        if (findingType !== 'All' && findingType !== 'document') return false;
        if (enabledTypes.size > 0 && !enabledTypes.has('document')) return false;
        return withinDate(row.timestamp, fromDate, toDate);
      }});

      filteredIntelRows = payload.tables.intelligence_rows.filter(row => {{
        if (seed !== 'All' && row.seed !== seed) return false;
        if (domain !== 'All' && row.domain !== domain) return false;
        if (findingType !== 'All' && row.type !== findingType) return false;
        if (enabledTypes.size > 0 && !enabledTypes.has(row.type)) return false;
        return withinDate(row.timestamp, fromDate, toDate);
      }});

      if (query) {{
        filteredPageRows = filteredPageRows.filter(row => matchesSearch(row, ['seed', 'domain', 'title', 'page_url', 'status', 'emails_count', 'documents_count']));
        filteredEmailRows = filteredEmailRows.filter(row => matchesSearch(row, ['seed', 'domain', 'value', 'page_url']));
        filteredDocumentRows = filteredDocumentRows.filter(row => matchesSearch(row, ['seed', 'domain', 'value', 'page_url']));
        filteredIntelRows = filteredIntelRows.filter(row => matchesSearch(row, ['seed', 'domain', 'type', 'severity', 'url', 'status', 'details']));
      }}

      filteredPageRows = sortRows(filteredPageRows, tableSortState.pages);
      filteredEmailRows = sortRows(filteredEmailRows, tableSortState.emails);
      filteredDocumentRows = sortRows(filteredDocumentRows, tableSortState.documents);
      filteredIntelRows = sortRows(filteredIntelRows, tableSortState.intel);

      saveFilterState();
      renderTables();
      renderPageDetails();
      renderPageGraph();
      renderLiveMonitor();
    }}

    function resetFilters() {{
      document.getElementById('seedFilter').value = 'All';
      document.getElementById('domainFilter').value = 'All';
      document.getElementById('findingTypeFilter').value = 'All';
      document.getElementById('fromDate').value = '';
      document.getElementById('toDate').value = '';
      document.getElementById('globalSearch').value = '';
      Array.from(document.querySelectorAll('.type-filter')).forEach(box => {{ box.checked = true; }});
      filteredPageRows = [...payload.tables.page_rows];
      filteredEmailRows = [...payload.tables.email_rows];
      filteredDocumentRows = [...payload.tables.document_rows];
      filteredIntelRows = [...payload.tables.intelligence_rows];
      selectedPageUrl = '';
      saveFilterState();
      renderTables();
      renderPageDetails();
      renderPageGraph();
    }}

    function applyGraphFilters() {{
      saveFilterState();
      renderPageGraph();
    }}

    function matchesSearch(row, keys) {{
      const query = (document.getElementById('globalSearch').value || '').trim().toLowerCase();
      if (!query) return true;
      const text = String(row.search_blob || keys.map(key => String(row[key] ?? '')).join(' ').toLowerCase());
      return text.includes(query);
    }}

    function showFindingsForPage(pageUrl) {{
      selectPage(pageUrl);
      const target = document.getElementById('pages-table');
      if (target) target.scrollIntoView({{behavior:'smooth', block:'start'}});
    }}

    function showIntelForPage(pageUrl) {{
      selectPage(pageUrl);
      const target = document.getElementById('intel-table');
      if (target) target.scrollIntoView({{behavior:'smooth', block:'start'}});
    }}

    function sortTable(tableName, key, type) {{
      const state = tableSortState[tableName];
      if (!state) return;
      if (state.key === key) {{
        state.dir = state.dir === 'asc' ? 'desc' : 'asc';
      }} else {{
        state.key = key;
        state.type = type;
        state.dir = 'asc';
      }}
      applyFilters();
    }}

    function sortRows(rows, state) {{
      const copy = [...rows];
      const key = state.key;
      const dir = state.dir === 'desc' ? -1 : 1;
      const type = state.type;
      copy.sort((a, b) => {{
        const av = a[key];
        const bv = b[key];
        if (type === 'number') return dir * ((Number(av) || 0) - (Number(bv) || 0));
        if (type === 'date') {{
          const aTs = Number(a.timestamp_ms || Date.parse(String(av || '0')) || 0);
          const bTs = Number(b.timestamp_ms || Date.parse(String(bv || '0')) || 0);
          return dir * (aTs - bTs);
        }}
        return dir * String(av ?? '').localeCompare(String(bv ?? ''));
      }});
      return copy;
    }}

    function selectPage(pageUrl) {{
      selectedPageUrl = pageUrl || '';
      saveFilterState();
      renderPageDetails();
      renderPageGraph();
    }}

    function handleRowKey(event, pageUrl) {{
      if (event.key === 'Enter' || event.key === ' ') {{
        event.preventDefault();
        selectPage(pageUrl);
      }}
    }}

    function detailPills(items) {{
      if (!items || items.length === 0) return '<span class="mono">none</span>';
      return items.map(item => `<span class="pill">${{escapeHtml(item)}}</span>`).join('');
    }}

    function renderPageDetails() {{
      const panel = document.getElementById('pageDetailsPanel');
      if (!selectedPageUrl) {{
        panel.innerHTML = 'Select a page in any table to inspect extracted artifacts.';
        return;
      }}
      const details = payload.tables.page_details[selectedPageUrl];
      if (!details) {{
        panel.innerHTML = `No page details available for ${{escapeHtml(selectedPageUrl)}}.`;
        return;
      }}

      const headers = Object.entries(details.security_headers || {{}});
      const headerHtml = headers.length === 0
        ? '<span class="mono">none</span>'
        : headers.map(([k, v]) => `<span class="pill">${{escapeHtml(k)}}: ${{escapeHtml(v)}}</span>`).join('');

      panel.innerHTML = `
        <div class="mono"><b>URL:</b> <a href="${{escapeHtml(selectedPageUrl)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(selectedPageUrl)}}</a></div>
        <div class="mono"><b>Seed:</b> ${{escapeHtml(details.seed || '')}} | <b>Domain:</b> ${{escapeHtml(details.domain || '')}}</div>
        <div class="mono"><b>Title:</b> ${{escapeHtml(details.title || '')}}</div>
        <div class="mono" style="margin-bottom:8px;"><b>Description:</b> ${{escapeHtml(details.description || '')}}</div>
        <div class="details-grid">
          <div class="card"><h3>Emails</h3>${{detailPills(details.emails)}}</div>
          <div class="card"><h3>Phones</h3>${{detailPills(details.phones)}}</div>
          <div class="card"><h3>Documents</h3>${{detailPills(details.documents)}}</div>
          <div class="card"><h3>Images</h3>${{detailPills(details.images)}}</div>
          <div class="card"><h3>JavaScript</h3>${{detailPills(details.javascript_assets)}}</div>
          <div class="card"><h3>Technologies</h3>${{detailPills(details.technologies)}}</div>
          <div class="card"><h3>Broken Links</h3>${{detailPills(details.broken_links)}}</div>
          <div class="card"><h3>Security Headers</h3>${{headerHtml}}</div>
        </div>
      `;
    }}

    function applySnapshotFilters() {{
      const type = document.getElementById('snapshotTypeFilter')?.value || 'all';
      const sort = document.getElementById('snapshotSort')?.value || 'type_asc';

      filteredSnapshotRows = snapshotRows.filter(row => type === 'all' || row.change_type === type);

      const cmpText = (a, b) => String(a || '').localeCompare(String(b || ''));
      filteredSnapshotRows.sort((a, b) => {{
        if (sort === 'type_asc') return cmpText(a.change_type, b.change_type) || cmpText(a.url, b.url);
        if (sort === 'type_desc') return cmpText(b.change_type, a.change_type) || cmpText(a.url, b.url);
        if (sort === 'url_desc') return cmpText(b.url, a.url);
        return cmpText(a.url, b.url);
      }});

      renderSnapshotTable();
    }}

    function renderSnapshotTable() {{
      const body = document.getElementById('snapshotChangesTbody');
      if (!body) return;
      if (filteredSnapshotRows.length === 0) {{
        body.innerHTML = '<tr><td colspan="7">No page-level snapshot changes</td></tr>';
      }} else {{
        body.innerHTML = filteredSnapshotRows.slice(0, 2000).map(row => {{
          const counts = row.finding_refs && row.finding_refs.counts_by_type ? row.finding_refs.counts_by_type : {{}};
          const countText = Object.keys(counts).length === 0
            ? 'none'
            : Object.entries(counts).map(([k,v]) => `${{k}}:${{v}}`).join(', ');
          return `<tr>
            <td><a href="${{escapeHtml(row.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(row.url)}}</a></td>
            <td>${{escapeHtml(row.change_type)}}</td>
            <td class="mono">${{escapeHtml(row.previous_content_hash || '')}}</td>
            <td class="mono">${{escapeHtml(row.current_content_hash || '')}}</td>
            <td>${{escapeHtml(row.previous_timestamp || '')}}</td>
            <td>${{escapeHtml(row.current_timestamp || '')}}</td>
            <td>
              <button onclick="showFindingsForPage('${{escapeHtml(row.url)}}')">Assets</button>
              <button onclick="showIntelForPage('${{escapeHtml(row.url)}}')">Intel</button>
              <div class="mono">${{escapeHtml(countText)}}</div>
            </td>
          </tr>`;
        }}).join('');
      }}
      const count = document.getElementById('snapshotCount');
      if (count) count.textContent = `Rows: ${{filteredSnapshotRows.length}}`;
    }}

    function renderTables() {{
      const pagesBody = document.getElementById('pagesTbody');
      if (filteredPageRows.length === 0) {{
        pagesBody.innerHTML = '<tr><td colspan="7">No rows</td></tr>';
      }} else {{
        pagesBody.innerHTML = filteredPageRows.slice(0, 2000).map(row =>
          `<tr tabindex="0" onclick="selectPage('${{escapeHtml(row.page_url)}}')" onkeydown="handleRowKey(event, '${{escapeHtml(row.page_url)}}')"><td>${{escapeHtml(row.seed)}}</td><td>${{escapeHtml(row.domain)}}</td><td>${{escapeHtml(row.title || '(untitled)')}}</td><td>${{escapeHtml(row.status)}}</td><td>${{escapeHtml(row.emails_count)}}</td><td>${{escapeHtml(row.documents_count)}}</td><td>${{escapeHtml(row.timestamp)}}</td></tr>`
        ).join('');
      }}

      const emailsBody = document.getElementById('emailsTbody');
      if (filteredEmailRows.length === 0) {{
        emailsBody.innerHTML = '<tr><td colspan="5">No rows</td></tr>';
      }} else {{
        emailsBody.innerHTML = filteredEmailRows.slice(0, 2000).map(row =>
          `<tr tabindex="0" onclick="selectPage('${{escapeHtml(row.page_url)}}')" onkeydown="handleRowKey(event, '${{escapeHtml(row.page_url)}}')"><td>${{escapeHtml(row.seed)}}</td><td>${{escapeHtml(row.domain)}}</td><td>${{escapeHtml(row.value)}}</td><td><a href="${{escapeHtml(row.page_url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(row.page_url)}}</a></td><td>${{escapeHtml(row.timestamp)}}</td></tr>`
        ).join('');
      }}

      const documentsBody = document.getElementById('documentsTbody');
      if (filteredDocumentRows.length === 0) {{
        documentsBody.innerHTML = '<tr><td colspan="5">No rows</td></tr>';
      }} else {{
        documentsBody.innerHTML = filteredDocumentRows.slice(0, 2000).map(row =>
          `<tr tabindex="0" onclick="selectPage('${{escapeHtml(row.page_url)}}')" onkeydown="handleRowKey(event, '${{escapeHtml(row.page_url)}}')"><td>${{escapeHtml(row.seed)}}</td><td>${{escapeHtml(row.domain)}}</td><td><a href="${{escapeHtml(row.value)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(row.value)}}</a></td><td><a href="${{escapeHtml(row.page_url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(row.page_url)}}</a></td><td>${{escapeHtml(row.timestamp)}}</td></tr>`
        ).join('');
      }}

      const intelBody = document.getElementById('intelTbody');
      if (filteredIntelRows.length === 0) {{
        intelBody.innerHTML = '<tr><td colspan="8">No rows</td></tr>';
      }} else {{
        intelBody.innerHTML = filteredIntelRows.slice(0, 2000).map(row =>
          `<tr tabindex="0" onclick="selectPage('${{escapeHtml(row.page_url || row.url)}}')" onkeydown="handleRowKey(event, '${{escapeHtml(row.page_url || row.url)}}')"><td>${{escapeHtml(row.seed)}}</td><td>${{escapeHtml(row.domain)}}</td><td>${{escapeHtml(row.type)}}</td><td><span class="sev-badge sev-${{escapeHtml((row.severity || 'low').toLowerCase())}}">${{escapeHtml(row.severity || 'low')}}</span></td><td><a href="${{escapeHtml(row.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(row.url)}}</a></td><td>${{escapeHtml(row.status)}}</td><td>${{escapeHtml(row.timestamp)}}</td><td>${{escapeHtml(row.details)}}</td></tr>`
        ).join('');
      }}

      document.getElementById('pagesCount').textContent = `Rows: ${{filteredPageRows.length}}`;
      document.getElementById('emailsCount').textContent = `Rows: ${{filteredEmailRows.length}}`;
      document.getElementById('documentsCount').textContent = `Rows: ${{filteredDocumentRows.length}}`;
      document.getElementById('intelCount').textContent = `Rows: ${{filteredIntelRows.length}}`;
    }}

    function escapeHtml(value) {{
      if (value === null || value === undefined) return '';
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function exportRows(rows, filename, format) {{
      if (!rows || rows.length === 0) return;
      if (format === 'json') {{
        const blob = new Blob([JSON.stringify(rows, null, 2)], {{type:'application/json'}});
        triggerDownload(blob, `${{filename}}.json`);
        return;
      }}

      const keys = Object.keys(rows[0]);
      const csv = [keys.join(',')]
        .concat(rows.map(r => keys.map(k => `"${{String(r[k] ?? '').replaceAll('"','""')}}"`).join(',')))
        .join('\n');
      const blob = new Blob([csv], {{type:'text/csv;charset=utf-8;'}});
      triggerDownload(blob, `${{filename}}.csv`);
    }}

    function triggerDownload(blob, fileName) {{
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }}

    function renderCharts() {{
      const cm = payload.charts.crawl_metrics;
      Plotly.newPlot('crawlMetricsPlot', [
        {{type:'bar', x:cm.labels, y:cm.values, marker:{{color:['#0f766e','#1d4ed8','#b45309','#334155']}}}}
      ], {{margin:{{t:20,r:10,l:55,b:70}}, yaxis:{{title:'Count'}}}}, {{responsive:true}});

      const ed = payload.charts.email_domains;
      Plotly.newPlot('emailDomainPlot', [
        {{type:'bar', x:ed.labels, y:ed.values, marker:{{color:'#1d4ed8'}}}}
      ], {{margin:{{t:20,r:10,l:55,b:90}}, yaxis:{{title:'Emails'}}}}, {{responsive:true}});

      const dt = payload.charts.document_types;
      Plotly.newPlot('documentTypePlot', [
        {{type:'pie', labels:dt.labels, values:dt.values, textinfo:'label+percent', hole:.38}}
      ], {{margin:{{t:20,r:10,l:10,b:10}}}}, {{responsive:true}});

      const tech = payload.charts.technologies;
      Plotly.newPlot('technologyPlot', [
        {{type:'bar', x:tech.labels, y:tech.values, marker:{{color:'#0ea5e9'}}}}
      ], {{margin:{{t:20,r:10,l:55,b:90}}, yaxis:{{title:'Occurrences'}}}}, {{responsive:true}});

      const ct = payload.charts.crawl_timing;
      Plotly.newPlot('crawlTimingPlot', [
        {{type:'bar', x:ct.labels, y:ct.values, marker:{{color:['#0f766e','#1d4ed8','#b45309','#334155','#0ea5e9']}}}}
      ], {{margin:{{t:20,r:10,l:55,b:90}}, yaxis:{{title:'Seconds'}}}}, {{responsive:true}});

      const tl = payload.charts.timeline;
      Plotly.newPlot('timelinePlot', [
        {{type:'scatter', mode:'lines+markers', x:tl.x, y:tl.y, line:{{color:'#0f766e', width:3}}, marker:{{size:8}}}}
      ], {{margin:{{t:20,r:10,l:55,b:60}}, xaxis:{{title:'Finished At (UTC)'}}, yaxis:{{title:'Cumulative Pages'}}}}, {{responsive:true}});

      const cg = payload.charts.graph;
      Plotly.newPlot('graphPlot', [
        {{
          type:'sankey',
          arrangement:'snap',
          node:{{label:cg.nodes, pad:16, thickness:18, color:'#93c5fd'}},
          link:{{source:cg.sources, target:cg.targets, value:cg.values, color:'rgba(30,64,175,0.35)'}}
        }}
      ], {{margin:{{t:20,r:10,l:10,b:10}}}}, {{responsive:true}});
    }}

    function pageGraphNodeColor(changeType) {{
      if (changeType === 'new') return '#16a34a';
      if (changeType === 'changed') return '#f59e0b';
      if (changeType === 'removed') return '#dc2626';
      return '#94a3b8';
    }}

    function renderPageGraph() {{
      const graph = payload.charts.page_graph || {{nodes: [], edges: []}};
      const layoutMode = document.getElementById('graphLayoutMode')?.value || 'force';
      const seed = document.getElementById('graphSeedFilter')?.value || 'All';
      const domain = document.getElementById('graphDomainFilter')?.value || 'All';
      const depthFilter = document.getElementById('graphDepthFilter')?.value || 'all';
      const linkTypeFilter = document.getElementById('graphLinkTypeFilter')?.value || 'all';
      const snapshotFilter = document.getElementById('graphSnapshotFilter')?.value || 'all';
      const query = (document.getElementById('graphSearch')?.value || '').trim().toLowerCase();
      const limit = Number(document.getElementById('graphNodeLimit')?.value || 120);

      let nodes = (graph.nodes || []).filter(node => {{
        if (seed !== 'All' && node.seed !== seed) return false;
        if (domain !== 'All' && node.domain !== domain) return false;
        if (depthFilter !== 'all' && String(node.depth ?? '99') !== depthFilter) return false;
        if (snapshotFilter !== 'all' && node.change_type !== snapshotFilter) return false;
        if (query) {{
          const text = `${{node.url || ''}} ${{node.domain || ''}}`.toLowerCase();
          if (!text.includes(query)) return false;
        }}
        return true;
      }});

      nodes = nodes.slice(0, Math.max(20, limit));
      const nodeSet = new Set(nodes.map(node => node.url));
      const edges = (graph.edges || []).filter(edge => {{
        if (!nodeSet.has(edge.source) || !nodeSet.has(edge.target)) return false;
        if (linkTypeFilter !== 'all' && edge.edge_type !== linkTypeFilter) return false;
        return true;
      }});

      if (nodes.length === 0) {{
        Plotly.newPlot('pageGraphPlot', [{{type:'scatter', mode:'text', x:[0], y:[0], text:['No graph nodes for active filters'], textfont:{{size:14}}}}], {{
          margin:{{t:20,r:10,l:20,b:20}},
          xaxis:{{visible:false}},
          yaxis:{{visible:false}},
        }}, {{responsive:true, scrollZoom:true}});
        const countEl = document.getElementById('pageGraphCount');
        if (countEl) countEl.textContent = 'Nodes: 0 | Edges: 0';
        return;
      }}

      const byUrl = Object.fromEntries(nodes.map(node => [node.url, node]));
      const edgeXInternal = [];
      const edgeYInternal = [];
      const edgeXExternal = [];
      const edgeYExternal = [];
      const useHierarchy = layoutMode === 'hierarchical';
      const xKey = useHierarchy ? 'hier_x' : 'force_x';
      const yKey = useHierarchy ? 'hier_y' : 'force_y';
      for (const edge of edges) {{
        const src = byUrl[edge.source];
        const tgt = byUrl[edge.target];
        if (!src || !tgt) continue;
        const sx = Number(src[xKey] ?? src.x ?? 0);
        const sy = Number(src[yKey] ?? src.y ?? 0);
        const tx = Number(tgt[xKey] ?? tgt.x ?? 0);
        const ty = Number(tgt[yKey] ?? tgt.y ?? 0);
        if (edge.edge_type === 'external') {{
          edgeXExternal.push(sx, tx, null);
          edgeYExternal.push(sy, ty, null);
        }} else {{
          edgeXInternal.push(sx, tx, null);
          edgeYInternal.push(sy, ty, null);
        }}
      }}

      const nodeTrace = {{
        type: 'scattergl',
        mode: 'markers',
        x: nodes.map(node => Number(node[xKey] ?? node.x ?? 0)),
        y: nodes.map(node => Number(node[yKey] ?? node.y ?? 0)),
        marker: {{
          size: nodes.map(node => node.url === selectedPageUrl ? Math.min(36, (node.size || 12) + 8) : (node.size || 12)),
          color: nodes.map(node => pageGraphNodeColor(node.change_type)),
          line: {{
            color: nodes.map(node => node.url === selectedPageUrl ? '#0f172a' : '#ffffff'),
            width: nodes.map(node => node.url === selectedPageUrl ? 2 : 1),
          }},
          opacity: 0.95,
        }},
        text: nodes.map(node => `${{node.domain}}<br>${{node.url}}<br>depth: ${{node.depth ?? 'n/a'}}<br>links: ${{node.out_degree || 0}} out / ${{node.in_degree || 0}} in`),
        hoverinfo: 'text',
        customdata: nodes.map(node => node.url),
      }};

      const traces = [];
      traces.push({{type:'scattergl', mode:'lines', x:edgeXInternal, y:edgeYInternal, line:{{width:1.1, color:'rgba(14,165,233,0.45)'}}, hoverinfo:'skip', name:'Internal links'}});
      traces.push({{type:'scattergl', mode:'lines', x:edgeXExternal, y:edgeYExternal, line:{{width:1.3, color:'rgba(239,68,68,0.5)'}}, hoverinfo:'skip', name:'External links'}});
      traces.push(nodeTrace);

      Plotly.newPlot('pageGraphPlot', traces, {{
        margin:{{t:20,r:10,l:20,b:20}},
        dragmode:'pan',
        xaxis:{{visible:false, title: useHierarchy ? 'Depth' : ''}},
        yaxis:{{visible:false, scaleanchor:'x', scaleratio:1}},
        showlegend:false,
      }}, {{responsive:true, scrollZoom:true, displaylogo:false}});

      const countEl = document.getElementById('pageGraphCount');
      if (countEl) {{
        const internalCount = edges.filter(edge => edge.edge_type !== 'external').length;
        const externalCount = edges.filter(edge => edge.edge_type === 'external').length;
        countEl.textContent = `Nodes: ${{nodes.length}} | Edges: ${{edges.length}} (internal: ${{internalCount}}, external: ${{externalCount}})`;
      }}

      const graphEl = document.getElementById('pageGraphPlot');
      if (graphEl) {{
        graphEl.on('plotly_click', (event) => {{
          const point = event?.points?.[0];
          if (!point || !point.customdata) return;
          selectPage(String(point.customdata));
        }});
      }}
    }}

    function renderPerformanceChart() {{
      const perf = payload.performance || {{}};
      const rows = perf.per_seed || [];
      if (rows.length === 0) {{
        Plotly.newPlot('performancePlot', [
          {{type:'bar', x:['none'], y:[0], marker:{{color:'#94a3b8'}}, name:'No Data'}}
        ], {{margin:{{t:20,r:10,l:50,b:50}}}}, {{responsive:true}});
        return;
      }}

      Plotly.newPlot('performancePlot', [
        {{type:'bar', x:rows.map(r => r.seed_url), y:rows.map(r => r.fetch_time_seconds || 0), name:'Fetch (s)', marker:{{color:'#0f766e'}}}},
        {{type:'bar', x:rows.map(r => r.seed_url), y:rows.map(r => r.extraction_time_seconds || 0), name:'Extraction (s)', marker:{{color:'#1d4ed8'}}}},
        {{type:'bar', x:rows.map(r => r.seed_url), y:rows.map(r => r.intelligence_collection_time_seconds || 0), name:'Intelligence (s)', marker:{{color:'#b45309'}}}}
      ], {{
        barmode:'group',
        margin:{{t:20,r:10,l:55,b:120}},
        xaxis:{{title:'Seed URL', tickangle:-25}},
        yaxis:{{title:'Seconds'}}
      }}, {{responsive:true}});
    }}

    function renderRiskPanel() {{
      const score = Number(payload.risk?.score || 0);
      const riskFill = document.getElementById('riskFill');
      if (riskFill) riskFill.style.width = `${{Math.max(0, Math.min(100, score))}}%`;
      const scoreText = document.getElementById('riskScoreText');
      if (scoreText) scoreText.textContent = `${{score}}%`;
    }}

    function renderGroupedFindings() {{
      const root = document.getElementById('intelGroups');
      if (!root) return;
      const grouped = payload.grouped_findings || {{}};
      const query = (document.getElementById('intelGroupSearch')?.value || '').trim().toLowerCase();
      const sections = Object.entries(grouped).map(([name, items]) => {{
        const rows = (items || []).filter(item => !query || String(item).toLowerCase().includes(query));
        const list = rows.length
          ? `<ul>${{rows.slice(0, 120).map(item => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>`
          : '<div class="mono">No matches</div>';
        return `<div class="card"><h3>${{escapeHtml(name)}} <span class="mono">(${{rows.length}})</span></h3><div class="group-list">${{list}}</div></div>`;
      }});
      root.innerHTML = sections.join('');
    }}

    function renderTechnologyList() {{
      const root = document.getElementById('technologyList');
      if (!root) return;
      const tech = payload.charts?.technologies || {{labels: [], values: []}};
      if (!tech.labels.length) {{
        root.innerHTML = '<div class="mono">No technology fingerprints detected.</div>';
        return;
      }}
      root.innerHTML = `<ul>${{tech.labels.map((label, idx) => `<li>${{escapeHtml(label)}} <span class="mono">(${{tech.values[idx] || 0}})</span></li>`).join('')}}</ul>`;
    }}

    function exportPdfReport() {{
      window.print();
    }}

    function exportMarkdownReport() {{
      const risk = payload.risk || {{score: 0, exposure: 'LOW', counts: {{}}}};
      const md = [
        '# OSINT Crawl Report',
        '',
        `Generated: ${{payload.generated_at}}`,
        '',
        '## Executive Summary',
        `- Pages Crawled: ${{payload.stats?.pages_crawled || 0}}`,
        `- Assets Found: ${{payload.derived?.assets_total || 0}}`,
        `- Emails: ${{payload.stats?.unique_emails || 0}}`,
        `- Documents: ${{payload.stats?.unique_documents || 0}}`,
        `- Risk Score: ${{risk.score || 0}}% (${{risk.exposure || 'LOW'}})`,
        '',
        '## Risk Breakdown',
        `- Info: ${{risk.counts?.info || 0}}`,
        `- Low: ${{risk.counts?.low || 0}}`,
        `- Medium: ${{risk.counts?.medium || 0}}`,
        `- High: ${{risk.counts?.high || 0}}`,
        `- Critical: ${{risk.counts?.critical || 0}}`,
        '',
        '## Top Technologies',
      ];
      const tech = payload.charts?.technologies || {{labels: [], values: []}};
      for (let i = 0; i < tech.labels.length; i += 1) {{
        md.push(`- ${{tech.labels[i]}}: ${{tech.values[i] || 0}}`);
      }}
      md.push('', '## Detection Modules');
      for (const item of (payload.detection_modules || [])) {{
        md.push(`- ${{item.name}}: ${{item.count}} (${{item.status}})`);
      }}
      const blob = new Blob([md.join('\n')], {{type:'text/markdown;charset=utf-8;'}});
      triggerDownload(blob, 'osint_report.md');
    }}

    function renderDetectionModules() {{
      const root = document.getElementById('detectionModules');
      if (!root) return;
      const modules = payload.detection_modules || [];
      if (!modules.length) {{
        root.innerHTML = '<div class="mono">No detection module data available.</div>';
        return;
      }}
      root.innerHTML = modules.map(item => `
        <div class="det-card">
          <h3>${{escapeHtml(item.name)}}</h3>
          <div><span class="det-status det-${{escapeHtml(item.status || 'ok')}}">${{escapeHtml((item.status || 'ok').toUpperCase())}}</span></div>
          <div style="margin-top:6px;"><b>${{escapeHtml(String(item.count || 0))}}</b></div>
          <div class="mono" style="margin-top:6px;">${{escapeHtml(item.description || '')}}</div>
        </div>
      `).join('');
    }}

    function renderScreenshotGallery() {{
      const root = document.getElementById('screenshotGallery');
      if (!root) return;
      const items = payload.screenshots || [];
      if (!items.length) {{
        root.innerHTML = '<div class="mono">No screenshots captured. Run with --collect-screenshots.</div>';
        return;
      }}
      root.innerHTML = items.slice(0, 120).map(item => `
        <div class="shot">
          <img src="${{escapeHtml(item.path)}}" alt="Screenshot for ${{escapeHtml(item.url || item.seed || '')}}" loading="lazy"/>
          <div class="meta">
            <div><b>${{escapeHtml(item.seed || '')}}</b></div>
            <div class="mono">${{escapeHtml(item.url || '')}}</div>
          </div>
        </div>
      `).join('');
    }}

    let liveStreamTimer = null;
    let liveSocket = null;
    let lastLiveSeq = 0;
    let liveEventBuffer = [];
    const liveAuthToken = payload.live_stream?.auth_token || '';

    function mergeLiveEvents(events) {{
      if (!events || !events.length) return;
      const fresh = events.filter(item => Number(item.sequence || 0) > lastLiveSeq);
      if (!fresh.length) return;
      lastLiveSeq = Number(fresh[fresh.length - 1].sequence || lastLiveSeq);
      liveEventBuffer = [...liveEventBuffer, ...fresh].slice(-300);
      applyLiveEvents();
    }}

    async function pollLiveStream() {{
      try {{
        const headers = liveAuthToken ? {{Authorization: `Bearer ${{liveAuthToken}}`}} : {{}};
        const apiResponse = await fetch(`/api/live/events?since=${{lastLiveSeq}}`, {{cache: 'no-store', headers}});
        if (apiResponse.ok) {{
          const data = await apiResponse.json();
          mergeLiveEvents(Array.isArray(data?.events) ? data.events : []);
          return;
        }}
      }} catch (_err) {{
        // fallback below
      }}

      const streamPath = payload.live_stream?.path;
      if (!streamPath) return;
      try {{
        const response = await fetch(streamPath + `?t=${{Date.now()}}`, {{cache: 'no-store'}});
        if (!response.ok) return;
        const text = await response.text();
        const lines = text.split('\n').filter(Boolean);
        const events = lines.map(line => {{
          try {{ return JSON.parse(line); }} catch (_err) {{ return null; }}
        }}).filter(Boolean);
        mergeLiveEvents(events);
      }} catch (_err) {{
        // Ignore polling errors when file is not served over HTTP.
      }}
    }}

    function connectLiveSocket() {{
      if (liveSocket || !window.WebSocket || !window.location?.host) return;
      const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
      try {{
        const query = liveAuthToken ? `?token=${{encodeURIComponent(liveAuthToken)}}` : '';
        liveSocket = new WebSocket(`${{scheme}}://${{window.location.host}}/ws/live${{query}}`);
      }} catch (_err) {{
        liveSocket = null;
        return;
      }}
      liveSocket.onmessage = (event) => {{
        try {{
          const data = JSON.parse(event.data);
          mergeLiveEvents(Array.isArray(data?.events) ? data.events : []);
        }} catch (_err) {{
          // ignore malformed frame
        }}
      }};
      liveSocket.onclose = () => {{
        liveSocket = null;
      }};
      liveSocket.onerror = () => {{
        liveSocket = null;
      }};
    }}

    function applyLiveEvents() {{
      if (!liveEventBuffer.length) return;
      const latest = liveEventBuffer[liveEventBuffer.length - 1];
      const pages = Number(latest.pages_crawled || latest.pages || payload.stats?.pages_crawled || 0);
      const maxPages = Number(payload.stats?.max_pages || payload.stats?.pages_crawled || pages || 1);
      const progress = maxPages > 0 ? Math.min(100, Math.round((pages / maxPages) * 100)) : 0;
      const queueDepth = Number(latest.queue_depth || 0);
      const depth = Number(latest.depth || payload.charts?.page_graph?.max_depth || 0);

      const setText = (id, value) => {{
        const el = document.getElementById(id);
        if (el) el.textContent = value;
      }};
      const fill = document.getElementById('monitorProgress');
      if (fill) fill.style.width = `${{progress}}%`;
      setText('monitorProgressText', `${{progress}}%`);
      setText('monitorPages', String(pages));
      setText('monitorQueue', String(queueDepth));
      setText('monitorDepth', String(depth));
      setText('monitorCurrentUrl', `Current URL: ${{latest.url || 'waiting...'}}`);

      const feed = document.getElementById('timelineFeed');
      if (feed) {{
        feed.innerHTML = liveEventBuffer.slice(-24).reverse().map(event => `
          <div class="feed-item">
            <div class="time">${{escapeHtml(String(event.timestamp || '').slice(11, 19) || '--:--:--')}}</div>
            <div>${{escapeHtml(String(event.event || 'event').replaceAll('_', ' '))}}${{event.url ? `: ${{escapeHtml(event.url)}}` : ''}}</div>
          </div>
        `).join('');
      }}
    }}

    function renderLiveMonitor() {{
      const timeline = payload.charts?.timeline || {{x: [], y: []}};
      const x = timeline.x || [];
      const y = timeline.y || [];
      const pages = Number(payload.stats?.pages_crawled || y[y.length - 1] || 0);
      const requestsCompleted = Number(payload.performance?.aggregate?.requests_completed || pages || 0);
      const duration = Number(payload.snapshot?.duration_seconds || 0);
      const rps = duration > 0 ? requestsCompleted / duration : 0;
      const maxPages = Number(payload.stats?.max_pages || pages || 1);
      const progress = maxPages > 0 ? Math.min(100, Math.round((pages / maxPages) * 100)) : 0;
      const queueSize = Math.max(0, maxPages - pages);
      const depth = Number(payload.charts?.page_graph?.max_depth || 0);
      const eta = rps > 0 ? (queueSize / rps) : 0;

      const progressBar = document.getElementById('monitorProgress');
      if (progressBar) progressBar.style.width = `${{progress}}%`;
      const setText = (id, value) => {{
        const el = document.getElementById(id);
        if (el) el.textContent = value;
      }};

      setText('monitorProgressText', `${{progress}}%`);
      setText('monitorPages', String(pages));
      setText('monitorRps', rps.toFixed(2));
      setText('monitorQueue', String(queueSize));
      setText('monitorDepth', String(depth));
      setText('monitorEta', eta > 0 ? `${{Math.ceil(eta)}}s` : 'n/a');

      const latest = filteredPageRows[0] || payload.tables?.page_rows?.[0] || null;
      const currentUrl = latest?.page_url || latest?.url || 'waiting...';
      setText('monitorCurrentUrl', `Current URL: ${{currentUrl}}`);

      const feed = document.getElementById('timelineFeed');
      if (feed) {{
        const events = [];
        for (let i = 0; i < x.length; i += 1) {{
          const ts = String(x[i] || '');
          const val = Number(y[i] || 0);
          events.push({{ ts, text: `Crawl progress reached ${{val}} pages` }});
        }}
        const startTs = x[0] || payload.generated_at;
        const endTs = x[x.length - 1] || payload.generated_at;
        events.unshift({{ ts: startTs, text: 'Started crawl' }});
        events.push({{ ts: endTs, text: 'Completed crawl' }});
        feed.innerHTML = events.slice(-24).reverse().map(event => `
          <div class="feed-item">
            <div class="time">${{escapeHtml(String(event.ts).slice(11, 19) || '--:--:--')}}</div>
            <div>${{escapeHtml(event.text)}}</div>
          </div>
        `).join('');
      }}

      if (!liveStreamTimer && payload.live_stream?.path) {{
        connectLiveSocket();
        liveStreamTimer = window.setInterval(pollLiveStream, 1250);
      }}
    }}

    applyTheme(localStorage.getItem(THEME_STATE_KEY) || 'light');
    populateFilters();
    applySnapshotFilters();
    renderCharts();
    renderRiskPanel();
    renderGroupedFindings();
    renderDetectionModules();
    renderScreenshotGallery();
    renderTechnologyList();
    renderPageGraph();
    renderPerformanceChart();
    applyFilters();
    renderLiveMonitor();
  </script>
</body>
</html>
"""

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def write_live_monitor_page(live_stream_path: str, output_path: str, *, auth_token: str = "") -> None:
    stream_ref = Path(live_stream_path).as_posix()
    html = f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>OSINT Live Crawl Monitor</title>
  <style>
    body {{ margin:0; padding:18px; font-family:'Segoe UI', Tahoma, sans-serif; background:#0b1220; color:#e2e8f0; }}
    .card {{ border:1px solid #24324a; border-radius:12px; padding:12px; background:#111a2b; margin-bottom:10px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; }}
    .tile {{ border:1px solid #24324a; border-radius:10px; padding:8px; background:#0f172a; }}
    .tile b {{ font-size:20px; display:block; margin-top:3px; }}
    .bar {{ height:12px; border-radius:999px; overflow:hidden; border:1px solid #24324a; background:#0f172a; }}
    .bar > div {{ height:100%; width:0%; background:linear-gradient(90deg,#06b6d4,#22c55e); transition:width .4s ease; }}
    .feed {{ max-height:420px; overflow:auto; border:1px solid #24324a; border-radius:10px; padding:8px; }}
    .event {{ margin:0 0 6px; font-family:Consolas, 'Courier New', monospace; font-size:12px; }}
  </style>
</head>
<body>
  <div class='card'>
    <h1 style='margin:0 0 6px;'>OSINT Live Crawl Monitor</h1>
    <div id='currentUrl'>Current URL: waiting...</div>
    <div class='bar' style='margin-top:8px;'><div id='progressFill'></div></div>
    <div class='grid' style='margin-top:10px;'>
      <div class='tile'><span>Progress</span><b id='progressText'>0%</b></div>
      <div class='tile'><span>Pages</span><b id='pagesText'>0</b></div>
      <div class='tile'><span>Queue</span><b id='queueText'>0</b></div>
      <div class='tile'><span>Depth</span><b id='depthText'>0</b></div>
    </div>
  </div>
  <div class='card'>
    <h2 style='margin:0 0 8px;'>Timeline</h2>
    <div id='eventFeed' class='feed'></div>
  </div>

  <script>
    const streamPath = {json.dumps(stream_ref, ensure_ascii=True)};
    const authToken = {json.dumps(auth_token, ensure_ascii=True)};
    let lastSeq = 0;
    let maxPages = 1;
    let feed = [];
    let socket = null;

    function setText(id, value) {{
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    }}

    function applyEvents(events) {{
      const fresh = events.filter(e => Number(e.sequence || 0) > lastSeq);
      if (!fresh.length) return;

      for (const event of fresh) {{
        lastSeq = Number(event.sequence || lastSeq);
        feed.push(event);
        if (event.event === 'crawl_started') {{
          maxPages = Math.max(1, Number(event.max_pages_per_seed || 1) * Number(event.seed_count || 1));
        }}
        if (event.event === 'page_crawled') {{
          const pages = Number(event.pages_crawled || 0);
          const progress = Math.min(100, Math.round((pages / maxPages) * 100));
          const fill = document.getElementById('progressFill');
          if (fill) fill.style.width = progress + '%';
          setText('progressText', progress + '%');
          setText('pagesText', String(pages));
          setText('queueText', String(Number(event.queue_depth || 0)));
          setText('depthText', String(Number(event.depth || 0)));
          setText('currentUrl', 'Current URL: ' + String(event.url || ''));
        }}
      }}

      const feedEl = document.getElementById('eventFeed');
      if (feedEl) {{
        feedEl.innerHTML = feed.slice(-120).reverse().map(event => (
          `<div class="event">${{String(event.timestamp || '').slice(11,19)}} | ${{String(event.event || '').replaceAll('_',' ')}}${{event.url ? ' | ' + event.url : ''}}</div>`
        )).join('');
      }}
    }}

    async function tick() {{
      try {{
        const apiHeaders = authToken ? {{Authorization: 'Bearer ' + authToken}} : {{}};
        const api = await fetch('/api/live/events?since=' + lastSeq, {{cache: 'no-store', headers: apiHeaders}});
        if (api.ok) {{
          const data = await api.json();
          applyEvents(Array.isArray(data?.events) ? data.events : []);
          return;
        }}

        const response = await fetch(streamPath + '?t=' + Date.now(), {{cache: 'no-store'}});
        if (!response.ok) return;
        const text = await response.text();
        const events = text.split('\\n').filter(Boolean).map(line => {{
          try {{ return JSON.parse(line); }} catch (_err) {{ return null; }}
        }}).filter(Boolean);
        applyEvents(events);
      }} catch (_err) {{
        // ignore polling errors
      }}
    }}

    function connectSocket() {{
      if (!window.WebSocket || !window.location?.host || socket) return;
      const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
      try {{
        const query = authToken ? `?token=${{encodeURIComponent(authToken)}}` : '';
        socket = new WebSocket(`${{scheme}}://${{window.location.host}}/ws/live${{query}}`);
      }} catch (_err) {{
        socket = null;
        return;
      }}
      socket.onmessage = (event) => {{
        try {{
          const data = JSON.parse(event.data);
          applyEvents(Array.isArray(data?.events) ? data.events : []);
        }} catch (_err) {{
          // ignore malformed socket frame
        }}
      }};
      socket.onclose = () => {{ socket = null; }};
      socket.onerror = () => {{ socket = null; }};
    }}

    window.setInterval(tick, 1000);
    connectSocket();
    tick();
  </script>
</body>
</html>
"""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def _render_error_rows(items: list[dict]) -> str:
    if not items:
        return "<tr><td colspan='2'>No crawl errors</td></tr>"
    rows = []
    for item in items[:400]:
        rows.append(f"<tr><td>{escape(item['seed'])}</td><td>{escape(item['error'])}</td></tr>")
    return "".join(rows)


def _render_snapshot_comparison(snapshot: dict) -> str:
    previous = str(snapshot.get("previous_run_id") or "")
    if not previous:
        return "<div class='mono'>No previous crawl snapshot available yet.</div>"

    details_block = """
    <div class='toolbar'>
      <div style='min-width:180px;'>
        <label for='snapshotTypeFilter'>Change Type</label>
        <select id='snapshotTypeFilter' onchange='applySnapshotFilters()'>
          <option value='all'>All</option>
          <option value='new'>New</option>
          <option value='changed'>Changed</option>
          <option value='removed'>Removed</option>
        </select>
      </div>
      <div style='min-width:180px;'>
        <label for='snapshotSort'>Sort</label>
        <select id='snapshotSort' onchange='applySnapshotFilters()'>
          <option value='type_asc'>Type (A-Z)</option>
          <option value='type_desc'>Type (Z-A)</option>
          <option value='url_asc'>URL (A-Z)</option>
          <option value='url_desc'>URL (Z-A)</option>
        </select>
      </div>
      <span id='snapshotCount' class='mono'></span>
    </div>
    <div class='scroll'>
      <table>
        <thead>
          <tr>
            <th>URL</th>
            <th>Change Type</th>
            <th>Previous Hash</th>
            <th>Current Hash</th>
            <th>Previous Timestamp</th>
            <th>Current Timestamp</th>
            <th>Findings</th>
          </tr>
        </thead>
        <tbody id='snapshotChangesTbody'></tbody>
      </table>
    </div>
    """

    return (
        "<div class='grid3'>"
        f"<div class='card'><h2>Previous Run</h2><div class='mono'>{escape(previous)}</div></div>"
        f"<div class='card'><h2>Run Duration</h2><div><b>{escape(str(snapshot.get('duration_seconds', 0.0)))}s</b></div></div>"
        f"<div class='card'><h2>Pages New</h2><div><b>{escape(str(snapshot.get('new_pages', 0)))}</b></div></div>"
        f"<div class='card'><h2>Pages Changed</h2><div><b>{escape(str(snapshot.get('changed_pages', 0)))}</b></div></div>"
        f"<div class='card'><h2>Pages Removed</h2><div><b>{escape(str(snapshot.get('removed_pages', 0)))}</b></div></div>"
        f"<div class='card'><h2>Findings New</h2><div><b>{escape(str(snapshot.get('new_findings', 0)))}</b></div></div>"
        f"<div class='card'><h2>Findings Removed</h2><div><b>{escape(str(snapshot.get('removed_findings', 0)))}</b></div></div>"
        "</div>"
        + details_block
    )


def _render_performance_summary(performance: dict) -> str:
    aggregate = performance.get("aggregate", {}) if isinstance(performance, dict) else {}
    return (
        "<div class='grid3'>"
        f"<div class='card'><h2>Requests Completed</h2><div><b>{escape(str(aggregate.get('requests_completed', 0)))}</b></div></div>"
        f"<div class='card'><h2>Avg Fetch</h2><div><b>{escape(str(aggregate.get('avg_fetch_time_ms', 0.0)))} ms</b></div></div>"
        f"<div class='card'><h2>Bytes Downloaded</h2><div><b>{escape(str(aggregate.get('bytes_downloaded', 0)))}</b></div></div>"
        f"<div class='card'><h2>Robots Time</h2><div><b>{escape(str(aggregate.get('robots_time_seconds', 0.0)))} s</b></div></div>"
        f"<div class='card'><h2>Extraction Time</h2><div><b>{escape(str(aggregate.get('extraction_time_seconds', 0.0)))} s</b></div></div>"
        f"<div class='card'><h2>Rate-Limit Wait</h2><div><b>{escape(str(aggregate.get('rate_limit_wait_seconds', 0.0)))} s</b></div></div>"
        "</div>"
    )


def _build_dashboard_payload(
  results: list[CrawlResult],
  stats: dict,
  *,
  live_stream_path: str = "",
  live_monitor_token: str = "",
) -> dict:
    seed_labels = [r.seed_url for r in results]
    seed_pages = [r.pages_crawled for r in results]
    seed_emails = [len(r.emails) for r in results]
    seed_docs = [len(r.documents) for r in results]

    domain_pages: Counter[str] = Counter()
    domain_links: Counter[str] = Counter()
    filetypes: Counter[str] = Counter()
    email_domains: Counter[str] = Counter()
    document_types: Counter[str] = Counter()
    technologies: Counter[str] = Counter()
    errors: list[dict] = []

    graph_edges: Counter[tuple[str, str]] = Counter()
    page_graph_edges: Counter[tuple[str, str, str]] = Counter()
    page_graph_nodes: dict[str, dict[str, object]] = {}
    page_in_degree: Counter[str] = Counter()
    page_out_degree: Counter[str] = Counter()
    page_intel_counts: Counter[str] = Counter()
    page_adjacency: dict[str, set[str]] = {}
    intelligence_rows: list[dict] = []
    assets_rows: list[dict] = []
    page_rows: list[dict] = []
    email_rows: list[dict] = []
    document_rows: list[dict] = []
    page_details: dict[str, dict] = {}

    seeds_filter: set[str] = set()
    domains_filter: set[str] = set()
    types_filter: set[str] = set()
    grouped_findings: dict[str, set[str]] = {
      "Email Addresses": set(),
      "Phone Numbers": set(),
      "Documents": set(),
      "Images": set(),
      "Technology": set(),
      "JavaScript": set(),
    }
    screenshots: list[dict[str, str]] = []
    sensitive_hits: set[str] = set()
    api_endpoint_hits: set[str] = set()
    directory_listing_hits: set[str] = set()
    metadata_hits: set[str] = set()
    tls_hits = 0
    missing_security_header_count = 0

    for result in results:
        seed = result.seed_url
        seeds_filter.add(seed)
        result_ts = (result.finished_at or result.started_at).isoformat()
        result_ts_ms = int((result.finished_at or result.started_at).timestamp() * 1000)

        for url in result.visited_urls:
            dom = (urlsplit(url).hostname or "unknown").lower()
            domains_filter.add(dom)
            domain_pages[dom] += 1

        for finding in result.page_findings:
            src_dom = (urlsplit(finding.url).hostname or "unknown").lower()
            domains_filter.add(src_dom)
            source_url = finding.url

            page_graph_nodes[source_url] = {
                "url": source_url,
                "label": (urlsplit(source_url).path or "/")[:72],
                "seed": seed,
                "domain": src_dom,
                "emails_count": len(finding.emails),
                "documents_count": len(finding.documents),
                "status": finding.http_status,
            }

            finding_types: list[str] = []
            if finding.emails:
                finding_types.append("email")
            if finding.documents:
                finding_types.append("document")
            if finding.images:
                finding_types.append("image")
            if finding.social_accounts:
                finding_types.append("social")
            if finding.phones:
                finding_types.append("phone")
            if finding.javascript_assets:
                finding_types.append("javascript")
            if finding.technologies:
                finding_types.append("technology")
            if finding.broken_links:
                finding_types.append("broken_link")
            if finding.security_headers:
                finding_types.append("security_header")

            page_rows.append(
                {
                    "seed": seed,
                    "domain": src_dom,
                    "page_url": finding.url,
                    "title": finding.title,
                    "status": finding.http_status,
                    "links_count": len(finding.links),
                    "emails_count": len(finding.emails),
                    "documents_count": len(finding.documents),
                    "timestamp": result_ts,
                "timestamp_ms": result_ts_ms,
                    "finding_types": finding_types,
                "search_blob": (
                  f"{seed} {src_dom} {finding.url} {finding.title} "
                  f"{finding.http_status} {len(finding.emails)} {len(finding.documents)}"
                ).lower(),
                }
            )
            page_details[finding.url] = {
                "seed": seed,
                "domain": src_dom,
                "title": finding.title,
                "description": finding.description,
                "keywords": list(finding.keywords),
                "emails": list(finding.emails),
                "phones": list(finding.phones),
                "documents": list(finding.documents),
                "images": list(finding.images),
                "javascript_assets": list(finding.javascript_assets),
                "technologies": list(finding.technologies),
                "security_headers": dict(finding.security_headers),
                "broken_links": list(finding.broken_links),
                "internal_links": list(finding.internal_links),
                "external_links": list(finding.external_links),
            }

            typed_links: list[tuple[str, str]] = []
            typed_links.extend((link, "internal") for link in finding.internal_links)
            typed_links.extend((link, "external") for link in finding.external_links)
            if not typed_links:
              typed_links.extend(
                (
                  link,
                  "internal"
                  if (urlsplit(link).hostname or "unknown").lower() == src_dom
                  else "external",
                )
                for link in finding.links
              )

            for link, edge_type in typed_links:
              tgt_dom = (urlsplit(link).hostname or "unknown").lower()
              graph_edges[(src_dom, tgt_dom)] += 1
              domain_links[tgt_dom] += 1
              domains_filter.add(tgt_dom)

              target_url = link
              page_graph_edges[(source_url, target_url, edge_type)] += 1
              page_out_degree[source_url] += 1
              page_in_degree[target_url] += 1
              page_adjacency.setdefault(source_url, set()).add(target_url)
              if target_url not in page_graph_nodes:
                page_graph_nodes[target_url] = {
                  "url": target_url,
                  "label": (urlsplit(target_url).path or "/")[:72],
                  "seed": seed,
                  "domain": tgt_dom,
                  "emails_count": 0,
                  "documents_count": 0,
                  "status": None,
                }

            for value in finding.emails:
                email_domain = (value.split("@", 1)[1].lower() if "@" in value else "unknown")
                email_domains[email_domain] += 1
                assets_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "asset_type": "email",
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    }
                )
                email_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    "timestamp_ms": result_ts_ms,
                    "search_blob": f"{seed} {src_dom} {value} {finding.url}".lower(),
                    }
                )
                types_filter.add("email")
                grouped_findings["Email Addresses"].add(value)

            for value in finding.documents:
                ext = _ext_for_url(value)
                filetypes[ext] += 1
                document_types[ext] += 1
                assets_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "asset_type": "document",
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    }
                )
                document_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    "timestamp_ms": result_ts_ms,
                    "search_blob": f"{seed} {src_dom} {value} {finding.url}".lower(),
                    }
                )
                types_filter.add("document")
                grouped_findings["Documents"].add(value)

            for value in finding.images:
                filetypes[_ext_for_url(value)] += 1
                assets_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "asset_type": "image",
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    }
                )
                types_filter.add("image")
                grouped_findings["Images"].add(value)

            for value in finding.social_accounts:
                assets_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "asset_type": "social",
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    }
                )
                types_filter.add("social")

            for value in finding.phones:
                assets_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "asset_type": "phone",
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    }
                )
                types_filter.add("phone")
                grouped_findings["Phone Numbers"].add(value)

            for value in finding.javascript_assets:
                filetypes[_ext_for_url(value)] += 1
                assets_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "asset_type": "javascript",
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    }
                )
                types_filter.add("javascript")
                grouped_findings["JavaScript"].add(value)

            for value in finding.technologies:
                assets_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "asset_type": "technology",
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    }
                )
                types_filter.add("technology")
                technologies[value] += 1
                grouped_findings["Technology"].add(value)

            for value in finding.broken_links:
                assets_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "asset_type": "broken_link",
                        "value": value,
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    }
                )
                types_filter.add("broken_link")

            for header_name, header_value in finding.security_headers.items():
                assets_rows.append(
                    {
                        "seed": seed,
                        "domain": src_dom,
                        "asset_type": "security_header",
                        "value": f"{header_name}: {header_value}",
                        "page_url": finding.url,
                        "timestamp": result_ts,
                    }
                )
                types_filter.add("security_header")

        for intel in result.intelligence_findings:
            dom = (urlsplit(intel.url).hostname or "unknown").lower()
            domains_filter.add(dom)
            types_filter.add(intel.finding_type)
            page_intel_counts[intel.url] += 1
            details_json = json.dumps(intel.details, sort_keys=True)
            severity = _infer_severity(intel.finding_type, details_json)
            intelligence_rows.append(
                {
                    "seed": seed,
                    "domain": dom,
                    "type": intel.finding_type,
                    "url": intel.url,
                    "status": intel.status,
                    "severity": severity,
                    "timestamp": result_ts,
                    "timestamp_ms": result_ts_ms,
                    "details": details_json,
                    "search_blob": (
                        f"{seed} {dom} {intel.finding_type} {intel.url} "
                        f"{intel.status} {severity} {details_json}"
                    ).lower(),
                }
            )

            lower_url = intel.url.lower()
            if any(token in lower_url for token in (".env", "backup", ".zip", ".bak", ".sql")):
                sensitive_hits.add(intel.url)
            if "/api" in lower_url:
                api_endpoint_hits.add(intel.url)
            if "directory" in details_json.lower() and "listing" in details_json.lower():
                directory_listing_hits.add(intel.url)
            if "metadata" in details_json.lower():
                metadata_hits.add(intel.url)
            if intel.finding_type == "tls_certificate" and intel.status == "ok":
                tls_hits += 1
            if intel.finding_type == "security_headers":
                header_details = intel.details.get("headers", {}) if isinstance(intel.details, dict) else {}
                if isinstance(header_details, dict) and len(header_details) < 3:
                    missing_security_header_count += 1
            if intel.finding_type == "screenshot":
                path_value = ""
                if isinstance(intel.details, dict):
                    path_value = str(intel.details.get("path", ""))
                if path_value:
                    screenshots.append(
                        {
                            "seed": seed,
                            "url": intel.url,
                            "path": path_value,
                        }
                    )

        for err in result.errors:
            errors.append({"seed": seed, "error": err})

    top_domains = domain_pages.most_common(12)
    graph_nodes = sorted({node for edge in graph_edges for node in edge})[:50]
    node_index = {node: idx for idx, node in enumerate(graph_nodes)}
    sources: list[int] = []
    targets: list[int] = []
    values: list[int] = []
    for (src, tgt), val in graph_edges.most_common(180):
        if src in node_index and tgt in node_index:
            sources.append(node_index[src])
            targets.append(node_index[tgt])
            values.append(val)

    timeline_items = sorted(results, key=lambda r: r.finished_at or r.started_at)
    timeline_x: list[str] = []
    timeline_y: list[int] = []
    running_pages = 0
    for item in timeline_items:
        running_pages += item.pages_crawled
        end = item.finished_at or item.started_at
        timeline_x.append(end.isoformat())
        timeline_y.append(running_pages)

    raw_snapshot = stats.get("snapshot_diff") if isinstance(stats, dict) else None
    snapshot = raw_snapshot if isinstance(raw_snapshot, dict) else {}
    raw_performance = stats.get("performance") if isinstance(stats, dict) else None
    performance = raw_performance if isinstance(raw_performance, dict) else {"aggregate": {}, "per_seed": []}
    snapshot_changes = list(snapshot.get("page_changes") or [])
    snapshot_change_map = {
      str(item.get("url") or ""): str(item.get("change_type") or "unchanged")
      for item in snapshot_changes
      if isinstance(item, dict)
    }

    def _coerce_int(value: object) -> int:
      if isinstance(value, bool):
        return 1 if value else 0
      if isinstance(value, int):
        return value
      if isinstance(value, float):
        return int(value)
      if isinstance(value, str):
        try:
          return int(value)
        except ValueError:
          return 0
      return 0

    page_depth: dict[str, int] = {}
    seed_start_nodes: dict[str, list[str]] = {}
    for url, node in page_graph_nodes.items():
      seed = str(node.get("seed") or "")
      if not seed:
        continue
      if url == seed:
        seed_start_nodes.setdefault(seed, []).append(url)

    if not seed_start_nodes:
      for url, node in page_graph_nodes.items():
        seed = str(node.get("seed") or "")
        if seed:
          seed_start_nodes.setdefault(seed, []).append(url)

    for starts in seed_start_nodes.values():
      queue: deque[str] = deque()
      chosen = sorted(set(starts))[:3]
      for start in chosen:
        if start not in page_depth:
          page_depth[start] = 0
          queue.append(start)
      while queue:
        current = queue.popleft()
        current_depth = page_depth.get(current, 0)
        for nxt in sorted(page_adjacency.get(current, set())):
          next_depth = current_depth + 1
          prev = page_depth.get(nxt)
          if prev is None or next_depth < prev:
            page_depth[nxt] = next_depth
            queue.append(nxt)

    for url in page_graph_nodes:
      if url not in page_depth:
        parts = [part for part in (urlsplit(url).path or "").split("/") if part]
        page_depth[url] = min(9, len(parts))

    page_graph_scored_nodes: list[dict[str, object]] = []
    for url, node in page_graph_nodes.items():
      in_degree = int(page_in_degree.get(url, 0))
      out_degree = int(page_out_degree.get(url, 0))
      intel_count = int(page_intel_counts.get(url, 0))
      emails_count = _coerce_int(node.get("emails_count", 0))
      documents_count = _coerce_int(node.get("documents_count", 0))
      depth = int(page_depth.get(url, 0))
      degree_total = in_degree + out_degree
      score = (degree_total * 3) + emails_count + documents_count + intel_count - depth
      page_graph_scored_nodes.append(
        {
          "url": url,
          "label": str(node.get("label") or "/"),
          "seed": str(node.get("seed") or ""),
          "domain": str(node.get("domain") or "unknown"),
          "in_degree": in_degree,
          "out_degree": out_degree,
          "intel_count": intel_count,
          "emails_count": emails_count,
          "documents_count": documents_count,
          "depth": depth,
          "change_type": snapshot_change_map.get(url, "unchanged"),
          "size": 10 + min(24, degree_total + emails_count + documents_count),
          "score": score,
        }
      )

    page_graph_scored_nodes.sort(key=lambda item: (_coerce_int(item["score"]), str(item["url"])), reverse=True)
    page_graph_nodes_limited = page_graph_scored_nodes[:420]
    page_graph_node_urls = {str(node["url"]) for node in page_graph_nodes_limited}

    page_graph_edges_rows: list[dict[str, object]] = []
    for (source, target, edge_type), weight in page_graph_edges.most_common(3200):
      if source in page_graph_node_urls and target in page_graph_node_urls:
        page_graph_edges_rows.append(
          {
            "source": source,
            "target": target,
            "edge_type": edge_type,
            "weight": int(weight),
          }
        )

    domains_for_layout = sorted({str(node["domain"]) for node in page_graph_nodes_limited})
    domain_positions = {
      domain: (
        1.5 * cos((2 * pi * idx) / max(1, len(domains_for_layout))),
        1.5 * sin((2 * pi * idx) / max(1, len(domains_for_layout))),
      )
      for idx, domain in enumerate(domains_for_layout)
    }

    node_urls = [str(node["url"]) for node in page_graph_nodes_limited]

    force_positions: dict[str, list[float]] = {}
    by_domain: dict[str, list[dict[str, object]]] = {}
    for node in page_graph_nodes_limited:
      by_domain.setdefault(str(node["domain"]), []).append(node)
    for domain_nodes in by_domain.values():
      domain_nodes.sort(key=lambda item: str(item["url"]))
    for domain in sorted(by_domain):
      cx, cy = domain_positions.get(domain, (0.0, 0.0))
      domain_nodes = by_domain[domain]
      total = max(1, len(domain_nodes))
      for idx, node in enumerate(domain_nodes):
        angle = (2 * pi * idx) / total
        radius = 0.35 + (0.08 * min(4, idx // 14))
        force_positions[str(node["url"])] = [cx + (radius * cos(angle)), cy + (radius * sin(angle))]

    edges_for_layout = [
      (str(edge["source"]), str(edge["target"]), _coerce_int(edge["weight"]))
      for edge in page_graph_edges_rows
      if str(edge["source"]) in force_positions and str(edge["target"]) in force_positions
    ]

    if node_urls:
      repulsion = 0.028
      spring_k = 0.035
      ideal_len = 0.9
      damping = 0.78
      for _ in range(26):
        disp = {url: [0.0, 0.0] for url in node_urls}

        for idx, a in enumerate(node_urls):
          ax, ay = force_positions[a]
          for b in node_urls[idx + 1 :]:
            bx, by = force_positions[b]
            dx = ax - bx
            dy = ay - by
            dist2 = (dx * dx) + (dy * dy) + 1e-6
            dist = dist2**0.5
            push = repulsion / dist2
            fx = (dx / dist) * push
            fy = (dy / dist) * push
            disp[a][0] += fx
            disp[a][1] += fy
            disp[b][0] -= fx
            disp[b][1] -= fy

        for source, target, weight in edges_for_layout:
          sx, sy = force_positions[source]
          tx, ty = force_positions[target]
          dx = tx - sx
          dy = ty - sy
          dist = ((dx * dx) + (dy * dy) + 1e-6) ** 0.5
          spring = spring_k * (dist - ideal_len) * min(3.0, 1.0 + (weight * 0.2))
          fx = (dx / dist) * spring
          fy = (dy / dist) * spring
          disp[source][0] += fx
          disp[source][1] += fy
          disp[target][0] -= fx
          disp[target][1] -= fy

        for url in node_urls:
          fx, fy = disp[url]
          force_positions[url][0] += max(-0.2, min(0.2, fx * damping))
          force_positions[url][1] += max(-0.2, min(0.2, fy * damping))

    depth_groups: dict[int, list[dict[str, object]]] = {}
    for node in page_graph_nodes_limited:
      depth_groups.setdefault(_coerce_int(node.get("depth", 0)), []).append(node)
    domain_rank = {domain: idx for idx, domain in enumerate(domains_for_layout)}

    max_depth = 0
    depth_values: list[int] = []
    for depth in sorted(depth_groups):
      nodes_at_depth = depth_groups[depth]
      nodes_at_depth.sort(key=lambda item: (str(item.get("domain") or ""), str(item["url"])))
      depth_values.append(depth)
      max_depth = max(max_depth, depth)
      total = max(1, len(nodes_at_depth))
      for idx, node in enumerate(nodes_at_depth):
        base_y = (idx - ((total - 1) / 2.0)) * 0.52
        offset = ((domain_rank.get(str(node.get("domain") or ""), 0) % 5) - 2) * 0.07
        node["hier_x"] = round(depth * 1.08, 6)
        node["hier_y"] = round(base_y + offset, 6)

    page_graph_nodes_with_layout: list[dict[str, object]] = []
    for node in page_graph_nodes_limited:
      url = str(node["url"])
      fx, fy = force_positions.get(url, [0.0, 0.0])
      node["force_x"] = round(fx, 6)
      node["force_y"] = round(fy, 6)
      node["x"] = node["force_x"]
      node["y"] = node["force_y"]
      if "hier_x" not in node:
        node["hier_x"] = 0.0
      if "hier_y" not in node:
        node["hier_y"] = 0.0
      page_graph_nodes_with_layout.append(node)

    risk_summary = _compute_risk_summary(
      intelligence_rows,
      int(stats.get("pages_crawled", 0) if isinstance(stats, dict) else 0),
    )

    grouped_findings_payload = {
      key: sorted(values)[:2000]
      for key, values in grouped_findings.items()
    }

    detection_modules = [
      {
        "name": "Sensitive Files",
        "count": len(sensitive_hits),
        "status": "high" if sensitive_hits else "ok",
        "description": "Potential .env/backups/archive artifacts discovered",
      },
      {
        "name": "Missing Security Headers",
        "count": missing_security_header_count,
        "status": "medium" if missing_security_header_count else "ok",
        "description": "Pages with weak or missing core hardening headers",
      },
      {
        "name": "API Endpoints",
        "count": len(api_endpoint_hits),
        "status": "medium" if api_endpoint_hits else "ok",
        "description": "URLs containing API-style paths",
      },
      {
        "name": "Directory Listings",
        "count": len(directory_listing_hits),
        "status": "high" if directory_listing_hits else "ok",
        "description": "Possible directory listing exposure indicators",
      },
      {
        "name": "Document Metadata",
        "count": len(metadata_hits),
        "status": "low" if metadata_hits else "ok",
        "description": "Potential metadata leakage in findings/details",
      },
      {
        "name": "TLS Coverage",
        "count": tls_hits,
        "status": "info" if tls_hits else "ok",
        "description": "Hosts with successfully collected TLS certificate details",
      },
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live_stream": {
            "path": live_stream_path,
          "auth_token": live_monitor_token,
        },
        "stats": stats,
        "risk": risk_summary,
        "snapshot": {
            "run_id": snapshot.get("run_id"),
            "previous_run_id": snapshot.get("previous_run_id"),
            "new_pages": int(snapshot.get("new_pages", 0) or 0),
            "removed_pages": int(snapshot.get("removed_pages", 0) or 0),
            "changed_pages": int(snapshot.get("changed_pages", 0) or 0),
            "new_findings": int(snapshot.get("new_findings", 0) or 0),
            "removed_findings": int(snapshot.get("removed_findings", 0) or 0),
            "duration_seconds": float(snapshot.get("duration_seconds", 0.0) or 0.0),
            "page_changes": snapshot_changes,
        },
        "performance": {
            "aggregate": dict(performance.get("aggregate") or {}),
            "per_seed": list(performance.get("per_seed") or []),
        },
        "derived": {
            "unique_domains": len(domain_pages),
          "assets_total": len(assets_rows),
          "unique_images": len(grouped_findings_payload.get("Images", [])),
          "unique_phones": len(grouped_findings_payload.get("Phone Numbers", [])),
        },
        "grouped_findings": grouped_findings_payload,
        "screenshots": screenshots,
        "detection_modules": detection_modules,
        "tables": {
          "page_rows": page_rows,
          "email_rows": email_rows,
          "document_rows": document_rows,
            "assets_rows": assets_rows,
            "intelligence_rows": intelligence_rows,
          "page_details": page_details,
        },
        "filters": {
            "seeds": sorted(seeds_filter),
            "domains": sorted(domains_filter),
            "finding_types": sorted(types_filter),
        },
        "errors": errors,
        "charts": {
          "crawl_metrics": {
            "labels": ["Pages", "Emails", "Documents", "Intelligence"],
            "values": [
              int(stats.get("pages_crawled", 0) if isinstance(stats, dict) else 0),
              int(stats.get("unique_emails", 0) if isinstance(stats, dict) else 0),
              int(stats.get("unique_documents", 0) if isinstance(stats, dict) else 0),
              int(stats.get("intelligence_findings", 0) if isinstance(stats, dict) else 0),
            ],
          },
          "email_domains": {
            "labels": [k for k, _ in email_domains.most_common(12)] or ["none"],
            "values": [v for _, v in email_domains.most_common(12)] or [0],
          },
          "document_types": {
            "labels": [k for k, _ in document_types.most_common(12)] or ["none"],
            "values": [v for _, v in document_types.most_common(12)] or [0],
          },
          "technologies": {
            "labels": [k for k, _ in technologies.most_common(16)] or ["none"],
            "values": [v for _, v in technologies.most_common(16)] or [0],
          },
          "crawl_timing": {
            "labels": [
              "Fetch",
              "Extraction",
              "Intelligence",
              "Robots",
              "Rate-limit wait",
            ],
            "values": [
              float(performance.get("aggregate", {}).get("fetch_time_seconds", 0.0) or 0.0),
              float(performance.get("aggregate", {}).get("extraction_time_seconds", 0.0) or 0.0),
              float(
                performance.get("aggregate", {}).get("intelligence_collection_time_seconds", 0.0)
                or 0.0
              ),
              float(performance.get("aggregate", {}).get("robots_time_seconds", 0.0) or 0.0),
              float(performance.get("aggregate", {}).get("rate_limit_wait_seconds", 0.0) or 0.0),
            ],
          },
            "seed": {
                "labels": seed_labels,
                "pages": seed_pages,
                "emails": seed_emails,
                "documents": seed_docs,
            },
            "domains": {
                "labels": [d for d, _ in top_domains],
                "pages": [v for _, v in top_domains],
                "links": [domain_links.get(d, 0) for d, _ in top_domains],
            },
            "filetypes": {
                "labels": [k for k, _ in filetypes.most_common(12)] or ["none"],
                "values": [v for _, v in filetypes.most_common(12)] or [1],
            },
            "timeline": {
                "x": timeline_x,
                "y": timeline_y,
            },
            "graph": {
                "nodes": graph_nodes or ["none"],
                "sources": sources or [0],
                "targets": targets or [0],
                "values": values or [1],
            },
            "page_graph": {
              "nodes": page_graph_nodes_with_layout,
              "edges": page_graph_edges_rows,
              "depth_values": depth_values,
              "max_depth": max_depth,
            },
        },
    }


def _ext_for_url(url: str) -> str:
    path = (urlsplit(url).path or "").lower()
    if "." not in path:
        return "unknown"
    return "." + path.rsplit(".", 1)[1]
