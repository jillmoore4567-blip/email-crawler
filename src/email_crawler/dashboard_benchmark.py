from __future__ import annotations

import json
from dataclasses import dataclass
from statistics import median
from time import perf_counter
from typing import Callable

RENDER_ROW_LIMIT = 2000
THRESHOLD_MS = 200.0


@dataclass(frozen=True)
class DashboardBenchmarkResult:
    rows: int
    page_load_ms: float
    search_latency_ms: float
    filter_latency_ms: float
    sort_latency_ms: float
    graph_render_ms: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "rows": self.rows,
            "page_load_ms": self.page_load_ms,
            "search_latency_ms": self.search_latency_ms,
            "filter_latency_ms": self.filter_latency_ms,
            "sort_latency_ms": self.sort_latency_ms,
            "graph_render_ms": self.graph_render_ms,
        }


def _measure_ms(fn: Callable[[], None], *, iterations: int = 7) -> float:
    samples: list[float] = []
    for _ in range(max(3, iterations)):
        started = perf_counter()
        fn()
        elapsed = (perf_counter() - started) * 1000.0
        samples.append(elapsed)
    return round(median(samples), 3)


def _object_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _str_list(value: object) -> list[str]:
    return [item for item in _object_list(value) if isinstance(item, str)]


def _int_value(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _float_value(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _generate_dataset(rows: int) -> dict[str, list[dict[str, object]]]:
    page_rows: list[dict[str, object]] = []
    email_rows: list[dict[str, object]] = []
    document_rows: list[dict[str, object]] = []
    intel_rows: list[dict[str, object]] = []
    page_graph_nodes: list[dict[str, object]] = []
    page_graph_edges: list[dict[str, object]] = []

    seeds = [f"http://seed{i}.example.test/index.html" for i in range(1, 6)]
    domains = [f"site{i}.example.test" for i in range(1, 11)]
    intel_types = ["robots_txt", "sitemap", "security_txt", "tech_fingerprint", "broken_link"]

    base_ts = 1_730_000_000_000
    for i in range(rows):
        seed = seeds[i % len(seeds)]
        domain = domains[i % len(domains)]
        page_url = f"https://{domain}/page-{i}.html"
        timestamp_ms = base_ts + (i * 1000)
        timestamp = f"2026-01-01T00:{i % 60:02d}:{(i // 60) % 60:02d}Z"

        page_row = {
            "seed": seed,
            "domain": domain,
            "page_url": page_url,
            "title": f"Synthetic Page {i}",
            "status": 200,
            "links_count": 20 + (i % 7),
            "emails_count": 1,
            "documents_count": 1,
            "timestamp": timestamp,
            "timestamp_ms": timestamp_ms,
            "finding_types": ["email", "document", "technology"],
            "search_blob": f"{seed} {domain} {page_url} synthetic page {i} email document technology",
        }
        page_rows.append(page_row)
        change_type = "unchanged"
        if i % 11 == 0:
            change_type = "changed"
        elif i % 17 == 0:
            change_type = "new"
        page_graph_nodes.append(
            {
                "url": page_url,
                "domain": domain,
                "seed": seed,
                "change_type": change_type,
                "depth": i % 6,
                "size": 10 + (i % 8),
                "force_x": round((i % 100) * 0.05, 4),
                "force_y": round((i // 100) * 0.05, 4),
                "hier_x": round((i % 6) * 1.0, 4),
                "hier_y": round(((i // 6) % 80) * 0.08, 4),
            }
        )
        if i > 0:
            prev_domain = domains[(i - 1) % len(domains)]
            prev_url = f"https://{prev_domain}/page-{i - 1}.html"
            page_graph_edges.append(
                {
                    "source": prev_url,
                    "target": page_url,
                    "weight": 1,
                    "edge_type": "internal" if prev_domain == domain else "external",
                }
            )
        if i > 4:
            parent_domain = domains[(i - 5) % len(domains)]
            parent_url = f"https://{parent_domain}/page-{i - 5}.html"
            page_graph_edges.append(
                {
                    "source": parent_url,
                    "target": page_url,
                    "weight": 1,
                    "edge_type": "internal" if parent_domain == domain else "external",
                }
            )

        email_rows.append(
            {
                "seed": seed,
                "domain": domain,
                "value": f"user{i}@{domain}",
                "page_url": page_url,
                "timestamp": timestamp,
                "timestamp_ms": timestamp_ms,
                "search_blob": f"{seed} {domain} user{i}@{domain} {page_url}",
            }
        )

        document_rows.append(
            {
                "seed": seed,
                "domain": domain,
                "value": f"https://{domain}/docs/doc-{i}.pdf",
                "page_url": page_url,
                "timestamp": timestamp,
                "timestamp_ms": timestamp_ms,
                "search_blob": f"{seed} {domain} doc-{i}.pdf {page_url}",
            }
        )

        intel_type = intel_types[i % len(intel_types)]
        intel_rows.append(
            {
                "seed": seed,
                "domain": domain,
                "type": intel_type,
                "url": page_url,
                "status": "ok",
                "timestamp": timestamp,
                "timestamp_ms": timestamp_ms,
                "details": json.dumps({"index": i, "type": intel_type}, sort_keys=True),
                "search_blob": f"{seed} {domain} {intel_type} {page_url} ok",
            }
        )

    return {
        "page_rows": page_rows,
        "email_rows": email_rows,
        "document_rows": document_rows,
        "intelligence_rows": intel_rows,
        "page_graph_nodes": page_graph_nodes,
        "page_graph_edges": page_graph_edges,
    }


def _render_rows(rows: list[dict[str, object]], keys: list[str]) -> str:
    subset = rows[:RENDER_ROW_LIMIT]
    return "".join(
        "<tr>" + "".join(f"<td>{str(row.get(key, ''))}</td>" for key in keys) + "</tr>" for row in subset
    )


def _page_load_operation(dataset: dict[str, list[dict[str, object]]]) -> None:
    _render_rows(
        dataset["page_rows"],
        ["seed", "domain", "title", "status", "emails_count", "documents_count", "timestamp"],
    )
    _render_rows(dataset["email_rows"], ["seed", "domain", "value", "page_url", "timestamp"])
    _render_rows(dataset["document_rows"], ["seed", "domain", "value", "page_url", "timestamp"])
    _render_rows(dataset["intelligence_rows"], ["seed", "domain", "type", "url", "status", "timestamp", "details"])


def _search_operation(dataset: dict[str, list[dict[str, object]]], query: str) -> None:
    q = query.lower()
    _ = [row for row in dataset["page_rows"] if q in str(row.get("search_blob", ""))]
    _ = [row for row in dataset["email_rows"] if q in str(row.get("search_blob", ""))]
    _ = [row for row in dataset["document_rows"] if q in str(row.get("search_blob", ""))]
    _ = [row for row in dataset["intelligence_rows"] if q in str(row.get("search_blob", ""))]


def _filter_operation(dataset: dict[str, list[dict[str, object]]]) -> None:
    seed = "http://seed1.example.test/index.html"
    domain = "site1.example.test"
    types = {"email", "document", "technology"}
    from_ts = 1_730_000_000_000
    to_ts = 1_740_000_000_000

    _ = [
        row
        for row in dataset["page_rows"]
        if row.get("seed") == seed
        and row.get("domain") == domain
        and any(t in types for t in _str_list(row.get("finding_types")))
        and from_ts <= _int_value(row.get("timestamp_ms")) <= to_ts
    ]

    _ = [
        row
        for row in dataset["email_rows"]
        if row.get("seed") == seed and row.get("domain") == domain and from_ts <= _int_value(row.get("timestamp_ms")) <= to_ts
    ]

    _ = [
        row
        for row in dataset["document_rows"]
        if row.get("seed") == seed and row.get("domain") == domain and from_ts <= _int_value(row.get("timestamp_ms")) <= to_ts
    ]

    _ = [
        row
        for row in dataset["intelligence_rows"]
        if row.get("seed") == seed
        and row.get("domain") == domain
        and row.get("type") in types
        and from_ts <= _int_value(row.get("timestamp_ms")) <= to_ts
    ]


def _sort_operation(dataset: dict[str, list[dict[str, object]]]) -> None:
    _ = sorted(dataset["page_rows"], key=lambda row: (str(row.get("title", "")), _int_value(row.get("timestamp_ms"))))
    _ = sorted(dataset["email_rows"], key=lambda row: str(row.get("value", "")))
    _ = sorted(dataset["document_rows"], key=lambda row: str(row.get("value", "")))
    _ = sorted(dataset["intelligence_rows"], key=lambda row: (str(row.get("type", "")), _int_value(row.get("timestamp_ms"))))


def _graph_render_operation(dataset: dict[str, list[dict[str, object]]]) -> None:
    nodes = [
        node
        for node in dataset["page_graph_nodes"]
        if node.get("seed") == "http://seed1.example.test/index.html"
        and node.get("domain") in {"site1.example.test", "site2.example.test", "site3.example.test"}
        and _int_value(node.get("depth")) <= 4
        and node.get("change_type") in {"changed", "new", "unchanged"}
    ]
    nodes = nodes[:120]
    node_urls = {str(node.get("url", "")) for node in nodes}
    by_url = {str(node.get("url", "")): node for node in nodes}

    force_internal_x: list[float | None] = []
    force_internal_y: list[float | None] = []
    force_external_x: list[float | None] = []
    force_external_y: list[float | None] = []
    hier_internal_x: list[float | None] = []
    hier_internal_y: list[float | None] = []
    hier_external_x: list[float | None] = []
    hier_external_y: list[float | None] = []

    for edge in dataset["page_graph_edges"]:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source not in node_urls or target not in node_urls:
            continue
        if edge.get("edge_type") not in {"internal", "external"}:
            continue
        src = by_url[source]
        tgt = by_url[target]
        sfx = _float_value(src.get("force_x"))
        sfy = _float_value(src.get("force_y"))
        tfx = _float_value(tgt.get("force_x"))
        tfy = _float_value(tgt.get("force_y"))
        shx = _float_value(src.get("hier_x"))
        shy = _float_value(src.get("hier_y"))
        thx = _float_value(tgt.get("hier_x"))
        thy = _float_value(tgt.get("hier_y"))

        if edge.get("edge_type") == "external":
            force_external_x.extend([sfx, tfx, None])
            force_external_y.extend([sfy, tfy, None])
            hier_external_x.extend([shx, thx, None])
            hier_external_y.extend([shy, thy, None])
        else:
            force_internal_x.extend([sfx, tfx, None])
            force_internal_y.extend([sfy, tfy, None])
            hier_internal_x.extend([shx, thx, None])
            hier_internal_y.extend([shy, thy, None])

    _ = {
        "force_internal_edge_points": (force_internal_x, force_internal_y),
        "force_external_edge_points": (force_external_x, force_external_y),
        "hier_internal_edge_points": (hier_internal_x, hier_internal_y),
        "hier_external_edge_points": (hier_external_x, hier_external_y),
        "force_node_points": (
            [_float_value(node.get("force_x")) for node in nodes],
            [_float_value(node.get("force_y")) for node in nodes],
        ),
        "hier_node_points": (
            [_float_value(node.get("hier_x")) for node in nodes],
            [_float_value(node.get("hier_y")) for node in nodes],
        ),
        "node_sizes": [_float_value(node.get("size"), 12.0) for node in nodes],
        "node_depths": [_int_value(node.get("depth")) for node in nodes],
        "node_colors": [str(node.get("change_type", "unchanged")) for node in nodes],
    }


def benchmark_dashboard_dataset(rows: int, *, iterations: int = 7) -> DashboardBenchmarkResult:
    dataset = _generate_dataset(rows)

    result = DashboardBenchmarkResult(
        rows=rows,
        page_load_ms=_measure_ms(lambda: _page_load_operation(dataset), iterations=iterations),
        search_latency_ms=_measure_ms(lambda: _search_operation(dataset, "site1 user1"), iterations=iterations),
        filter_latency_ms=_measure_ms(lambda: _filter_operation(dataset), iterations=iterations),
        sort_latency_ms=_measure_ms(lambda: _sort_operation(dataset), iterations=iterations),
        graph_render_ms=_measure_ms(lambda: _graph_render_operation(dataset), iterations=iterations),
    )

    return result


def run_dashboard_benchmarks(*, sizes: list[int] | None = None, iterations: int = 7) -> list[DashboardBenchmarkResult]:
    targets = sizes or [1000, 5000, 10000]
    return [benchmark_dashboard_dataset(size, iterations=iterations) for size in targets]


def has_regression(results: list[DashboardBenchmarkResult], *, threshold_ms: float = THRESHOLD_MS) -> list[str]:
    failures: list[str] = []
    for row in results:
        payload = row.as_dict()
        for metric in ("page_load_ms", "search_latency_ms", "filter_latency_ms", "sort_latency_ms", "graph_render_ms"):
            value = float(payload[metric])
            if value > threshold_ms:
                failures.append(f"rows={row.rows} metric={metric} value={value:.3f}ms threshold={threshold_ms:.3f}ms")
    return failures
