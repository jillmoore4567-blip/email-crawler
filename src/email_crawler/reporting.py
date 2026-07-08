from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from .crawler import CrawlResult


def write_html_report(results: list[CrawlResult], stats: dict, output_path: str) -> None:
    payload = _build_dashboard_payload(results, stats)

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
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:12px; box-shadow:0 4px 18px rgba(31,41,55,.06); }}
    .card h2 {{ margin:0 0 8px; font-size:17px; }}
    .plot {{ width:100%; height:340px; }}
    .plotTall {{ width:100%; height:420px; }}
    .toolbar {{ margin:6px 0 8px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
    button {{ border:1px solid var(--line); background:#fff; color:var(--ink); border-radius:8px; padding:6px 10px; cursor:pointer; }}
    button:hover {{ border-color:#b8c6da; background:#f9fbff; }}
    label {{ font-size:12px; color:var(--muted); display:block; margin-bottom:4px; }}
    select,input {{ width:100%; border:1px solid var(--line); border-radius:8px; padding:8px; background:#fff; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ border-bottom:1px solid var(--line); padding:7px 6px; text-align:left; vertical-align:top; }}
    th {{ color:#0b2447; background:#f7fafd; position:sticky; top:0; }}
    .scroll {{ max-height:320px; overflow:auto; border:1px solid var(--line); border-radius:10px; }}
    .pill {{ display:inline-block; margin:2px 4px 2px 0; padding:2px 7px; border:1px solid var(--line); border-radius:999px; font-size:12px; background:#f8fafc; }}
    .mono {{ font-family:Consolas, 'Courier New', monospace; font-size:12px; color:var(--muted); }}
    @media (max-width: 950px) {{ .grid2 {{ grid-template-columns:1fr; }} .grid3 {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <div class='wrap'>
    <section class='top'>
      <h1>OSINT Crawl Dashboard</h1>
      <div class='sub'>Generated {escape(payload['generated_at'])} | Authorized asset discovery summary</div>
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
    </section>

    <section class='grid2'>
      <div class='card'>
        <h2>Crawl Statistics</h2>
        <div class='toolbar'><button onclick="exportChart('seedStatsPlot','seed_stats')">Export Chart</button></div>
        <div id='seedStatsPlot' class='plot'></div>
      </div>
      <div class='card'>
        <h2>Domain Statistics</h2>
        <div class='toolbar'><button onclick="exportChart('domainPlot','domain_stats')">Export Chart</button></div>
        <div id='domainPlot' class='plot'></div>
      </div>
    </section>

    <section class='grid2'>
      <div class='card'>
        <h2>File-Type Statistics</h2>
        <div class='toolbar'><button onclick="exportChart('fileTypePlot','file_type_stats')">Export Chart</button></div>
        <div id='fileTypePlot' class='plot'></div>
      </div>
      <div class='card'>
        <h2>Crawl Timeline</h2>
        <div class='toolbar'><button onclick="exportChart('timelinePlot','crawl_timeline')">Export Chart</button></div>
        <div id='timelinePlot' class='plot'></div>
      </div>
    </section>

    <section class='card'>
      <h2>Crawl Graph (Domain Flow)</h2>
      <div class='toolbar'><button onclick="exportChart('graphPlot','crawl_graph')">Export Chart</button></div>
      <div id='graphPlot' class='plotTall'></div>
      <div class='mono'>Sankey edges are aggregated from discovered source-domain -> target-domain links.</div>
    </section>

    <section class='grid2'>
      <div id='assets-table' class='card'>
        <h2>Assets Table</h2>
        <div class='toolbar'>
          <button onclick="exportRows(filteredAssetsRows, 'assets_filtered', 'csv')">Export CSV</button>
          <button onclick="exportRows(filteredAssetsRows, 'assets_filtered', 'json')">Export JSON</button>
          <span id='assetsCount' class='mono'></span>
        </div>
        <div class='scroll'>
          <table>
            <thead><tr><th>Seed</th><th>Domain</th><th>Type</th><th>Value</th><th>Page URL</th><th>Timestamp</th></tr></thead>
            <tbody id='assetsTbody'></tbody>
          </table>
        </div>
      </div>

      <div id='intel-table' class='card'>
        <h2>Intelligence Findings Table</h2>
        <div class='toolbar'>
          <button onclick="exportRows(filteredIntelRows, 'intelligence_filtered', 'csv')">Export CSV</button>
          <button onclick="exportRows(filteredIntelRows, 'intelligence_filtered', 'json')">Export JSON</button>
          <span id='intelCount' class='mono'></span>
        </div>
        <div class='scroll'>
          <table>
            <thead><tr><th>Seed</th><th>Domain</th><th>Type</th><th>URL</th><th>Status</th><th>Timestamp</th><th>Details</th></tr></thead>
            <tbody id='intelTbody'></tbody>
          </table>
        </div>
      </div>
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
    let filteredAssetsRows = [...payload.tables.assets_rows];
    let filteredIntelRows = [...payload.tables.intelligence_rows];
    let pageUrlQuickFilter = '';
    let snapshotRows = [...(payload.snapshot.page_changes || [])];
    let filteredSnapshotRows = [...snapshotRows];

    function exportChart(divId, filename) {{
      Plotly.downloadImage(divId, {{format:'png', filename:filename, width:1200, height:700, scale:2}});
    }}

    function populateFilters() {{
      fillSelect('seedFilter', payload.filters.seeds);
      fillSelect('domainFilter', payload.filters.domains);
      fillSelect('findingTypeFilter', payload.filters.finding_types);
    }}

    function fillSelect(id, options) {{
      const el = document.getElementById(id);
      const merged = ['All', ...options];
      el.innerHTML = merged.map(v => `<option value="${{escapeHtml(v)}}">${{escapeHtml(v)}}</option>`).join('');
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

      filteredIntelRows = payload.tables.intelligence_rows.filter(row => {{
        if (seed !== 'All' && row.seed !== seed) return false;
        if (domain !== 'All' && row.domain !== domain) return false;
        if (findingType !== 'All' && row.type !== findingType) return false;
        if (pageUrlQuickFilter && !matchesIntelPage(row, pageUrlQuickFilter)) return false;
        return withinDate(row.timestamp, fromDate, toDate);
      }});

      filteredAssetsRows = payload.tables.assets_rows.filter(row => {{
        if (seed !== 'All' && row.seed !== seed) return false;
        if (domain !== 'All' && row.domain !== domain) return false;
        if (findingType !== 'All' && row.asset_type !== findingType) return false;
        if (pageUrlQuickFilter && row.page_url !== pageUrlQuickFilter) return false;
        return withinDate(row.timestamp, fromDate, toDate);
      }});

      renderTables();
    }}

    function resetFilters() {{
      document.getElementById('seedFilter').value = 'All';
      document.getElementById('domainFilter').value = 'All';
      document.getElementById('findingTypeFilter').value = 'All';
      document.getElementById('fromDate').value = '';
      document.getElementById('toDate').value = '';
      pageUrlQuickFilter = '';
      filteredAssetsRows = [...payload.tables.assets_rows];
      filteredIntelRows = [...payload.tables.intelligence_rows];
      renderTables();
    }}

    function matchesIntelPage(row, pageUrl) {{
      if (!pageUrl) return true;
      if (row.url === pageUrl) return true;
      const details = String(row.details || '');
      return details.includes(pageUrl);
    }}

    function showFindingsForPage(pageUrl) {{
      pageUrlQuickFilter = pageUrl || '';
      applyFilters();
      const target = document.getElementById('assets-table');
      if (target) target.scrollIntoView({{behavior:'smooth', block:'start'}});
    }}

    function showIntelForPage(pageUrl) {{
      pageUrlQuickFilter = pageUrl || '';
      applyFilters();
      const target = document.getElementById('intel-table');
      if (target) target.scrollIntoView({{behavior:'smooth', block:'start'}});
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
      const assetsBody = document.getElementById('assetsTbody');
      if (filteredAssetsRows.length === 0) {{
        assetsBody.innerHTML = '<tr><td colspan="6">No rows</td></tr>';
      }} else {{
        assetsBody.innerHTML = filteredAssetsRows.slice(0, 1000).map(row =>
          `<tr><td>${{escapeHtml(row.seed)}}</td><td>${{escapeHtml(row.domain)}}</td><td>${{escapeHtml(row.asset_type)}}</td><td>${{escapeHtml(row.value)}}</td><td><a href="${{escapeHtml(row.page_url)}}">${{escapeHtml(row.page_url)}}</a></td><td>${{escapeHtml(row.timestamp)}}</td></tr>`
        ).join('');
      }}

      const intelBody = document.getElementById('intelTbody');
      if (filteredIntelRows.length === 0) {{
        intelBody.innerHTML = '<tr><td colspan="7">No rows</td></tr>';
      }} else {{
        intelBody.innerHTML = filteredIntelRows.slice(0, 1000).map(row =>
          `<tr><td>${{escapeHtml(row.seed)}}</td><td>${{escapeHtml(row.domain)}}</td><td>${{escapeHtml(row.type)}}</td><td><a href="${{escapeHtml(row.url)}}">${{escapeHtml(row.url)}}</a></td><td>${{escapeHtml(row.status)}}</td><td>${{escapeHtml(row.timestamp)}}</td><td>${{escapeHtml(row.details)}}</td></tr>`
        ).join('');
      }}

      document.getElementById('assetsCount').textContent = `Rows: ${{filteredAssetsRows.length}}`;
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
      const seed = payload.charts.seed;
      Plotly.newPlot('seedStatsPlot', [
        {{type:'bar', x:seed.labels, y:seed.pages, name:'Pages', marker:{{color:'#0f766e'}}}},
        {{type:'bar', x:seed.labels, y:seed.emails, name:'Emails', marker:{{color:'#1d4ed8'}}}},
        {{type:'bar', x:seed.labels, y:seed.documents, name:'Documents', marker:{{color:'#b45309'}}}}
      ], {{barmode:'group', margin:{{t:20,r:10,l:50,b:70}}}}, {{responsive:true}});

      const dom = payload.charts.domains;
      Plotly.newPlot('domainPlot', [
        {{type:'bar', x:dom.labels, y:dom.pages, name:'Pages', marker:{{color:'#334155'}}}},
        {{type:'bar', x:dom.labels, y:dom.links, name:'Discovered Links', marker:{{color:'#0ea5e9'}}}}
      ], {{barmode:'group', margin:{{t:20,r:10,l:50,b:90}}}}, {{responsive:true}});

      const ft = payload.charts.filetypes;
      Plotly.newPlot('fileTypePlot', [
        {{type:'pie', labels:ft.labels, values:ft.values, textinfo:'label+percent', hole:.38}}
      ], {{margin:{{t:20,r:10,l:10,b:10}}}}, {{responsive:true}});

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

    populateFilters();
    applySnapshotFilters();
    renderCharts();
    renderPerformanceChart();
    renderTables();
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


def _build_dashboard_payload(results: list[CrawlResult], stats: dict) -> dict:
    seed_labels = [r.seed_url for r in results]
    seed_pages = [r.pages_crawled for r in results]
    seed_emails = [len(r.emails) for r in results]
    seed_docs = [len(r.documents) for r in results]

    domain_pages: Counter[str] = Counter()
    domain_links: Counter[str] = Counter()
    filetypes: Counter[str] = Counter()
    errors: list[dict] = []

    graph_edges: Counter[tuple[str, str]] = Counter()
    intelligence_rows: list[dict] = []
    assets_rows: list[dict] = []

    seeds_filter: set[str] = set()
    domains_filter: set[str] = set()
    types_filter: set[str] = set()

    for result in results:
        seed = result.seed_url
        seeds_filter.add(seed)
        result_ts = (result.finished_at or result.started_at).isoformat()

        for url in result.visited_urls:
            dom = (urlsplit(url).hostname or "unknown").lower()
            domains_filter.add(dom)
            domain_pages[dom] += 1

        for finding in result.page_findings:
            src_dom = (urlsplit(finding.url).hostname or "unknown").lower()
            domains_filter.add(src_dom)
            for link in finding.links:
                tgt_dom = (urlsplit(link).hostname or "unknown").lower()
                graph_edges[(src_dom, tgt_dom)] += 1
                domain_links[tgt_dom] += 1
                domains_filter.add(tgt_dom)

            for value in finding.emails:
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
                types_filter.add("email")

            for value in finding.documents:
                ext = _ext_for_url(value)
                filetypes[ext] += 1
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
                types_filter.add("document")

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
            intelligence_rows.append(
                {
                    "seed": seed,
                    "domain": dom,
                    "type": intel.finding_type,
                    "url": intel.url,
                    "status": intel.status,
                    "timestamp": result_ts,
                    "details": json.dumps(intel.details, sort_keys=True),
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

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "snapshot": {
            "run_id": snapshot.get("run_id"),
            "previous_run_id": snapshot.get("previous_run_id"),
            "new_pages": int(snapshot.get("new_pages", 0) or 0),
            "removed_pages": int(snapshot.get("removed_pages", 0) or 0),
            "changed_pages": int(snapshot.get("changed_pages", 0) or 0),
            "new_findings": int(snapshot.get("new_findings", 0) or 0),
            "removed_findings": int(snapshot.get("removed_findings", 0) or 0),
            "duration_seconds": float(snapshot.get("duration_seconds", 0.0) or 0.0),
          "page_changes": list(snapshot.get("page_changes") or []),
        },
        "performance": {
            "aggregate": dict(performance.get("aggregate") or {}),
            "per_seed": list(performance.get("per_seed") or []),
        },
        "derived": {
            "unique_domains": len(domain_pages),
        },
        "tables": {
            "assets_rows": assets_rows,
            "intelligence_rows": intelligence_rows,
        },
        "filters": {
            "seeds": sorted(seeds_filter),
            "domains": sorted(domains_filter),
            "finding_types": sorted(types_filter),
        },
        "errors": errors,
        "charts": {
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
        },
    }


def _ext_for_url(url: str) -> str:
    path = (urlsplit(url).path or "").lower()
    if "." not in path:
        return "unknown"
    return "." + path.rsplit(".", 1)[1]
