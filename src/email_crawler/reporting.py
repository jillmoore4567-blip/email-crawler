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
    .clickable {{ cursor:pointer; user-select:none; }}
    .clickable::after {{ content:' ↕'; font-size:11px; color:#64748b; }}
    tr[tabindex='0']:focus {{ outline:2px solid #93c5fd; outline-offset:-2px; }}
    .type-filters {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .type-filters label {{ display:flex; align-items:center; gap:6px; margin:0; border:1px solid var(--line); border-radius:999px; padding:5px 8px; background:#fff; }}
    .type-filters input {{ width:auto; }}
    .details-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:8px; }}
    .details-grid .card h3 {{ margin:0 0 6px; font-size:14px; }}
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
            <thead><tr><th class='clickable' onclick="sortTable('intel','seed','text')">Seed</th><th class='clickable' onclick="sortTable('intel','domain','text')">Domain</th><th class='clickable' onclick="sortTable('intel','type','text')">Type</th><th>URL</th><th class='clickable' onclick="sortTable('intel','status','text')">Status</th><th class='clickable' onclick="sortTable('intel','timestamp','date')">Timestamp</th><th>Details</th></tr></thead>
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

    let filteredPageRows = [...payload.tables.page_rows];
    let filteredEmailRows = [...payload.tables.email_rows];
    let filteredDocumentRows = [...payload.tables.document_rows];
    let filteredIntelRows = [...payload.tables.intelligence_rows];
    let selectedPageUrl = '';
    let snapshotRows = [...(payload.snapshot.page_changes || [])];
    let filteredSnapshotRows = [...snapshotRows];
    const tableSortState = {{
      pages: {{key: 'timestamp', dir: 'desc', type: 'date'}},
      emails: {{key: 'timestamp', dir: 'desc', type: 'date'}},
      documents: {{key: 'timestamp', dir: 'desc', type: 'date'}},
      intel: {{key: 'timestamp', dir: 'desc', type: 'date'}},
    }};

    function exportChart(divId, filename) {{
      Plotly.downloadImage(divId, {{format:'png', filename:filename, width:1200, height:700, scale:2}});
    }}

    function populateFilters() {{
      fillSelect('seedFilter', payload.filters.seeds);
      fillSelect('domainFilter', payload.filters.domains);
      fillSelect('findingTypeFilter', payload.filters.finding_types);
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
        filteredIntelRows = filteredIntelRows.filter(row => matchesSearch(row, ['seed', 'domain', 'type', 'url', 'status', 'details']));
      }}

      filteredPageRows = sortRows(filteredPageRows, tableSortState.pages);
      filteredEmailRows = sortRows(filteredEmailRows, tableSortState.emails);
      filteredDocumentRows = sortRows(filteredDocumentRows, tableSortState.documents);
      filteredIntelRows = sortRows(filteredIntelRows, tableSortState.intel);

      saveFilterState();
      renderTables();
      renderPageDetails();
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
        intelBody.innerHTML = '<tr><td colspan="7">No rows</td></tr>';
      }} else {{
        intelBody.innerHTML = filteredIntelRows.slice(0, 2000).map(row =>
          `<tr><td>${{escapeHtml(row.seed)}}</td><td>${{escapeHtml(row.domain)}}</td><td>${{escapeHtml(row.type)}}</td><td><a href="${{escapeHtml(row.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(row.url)}}</a></td><td>${{escapeHtml(row.status)}}</td><td>${{escapeHtml(row.timestamp)}}</td><td>${{escapeHtml(row.details)}}</td></tr>`
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
    applyFilters();
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
    page_rows: list[dict] = []
    email_rows: list[dict] = []
    document_rows: list[dict] = []
    page_details: dict[str, dict] = {}

    seeds_filter: set[str] = set()
    domains_filter: set[str] = set()
    types_filter: set[str] = set()

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
                "timestamp_ms": result_ts_ms,
                    "details": json.dumps(intel.details, sort_keys=True),
                "search_blob": (
                  f"{seed} {dom} {intel.finding_type} {intel.url} "
                  f"{intel.status} {json.dumps(intel.details, sort_keys=True)}"
                ).lower(),
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
