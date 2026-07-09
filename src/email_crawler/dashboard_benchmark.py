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

    def as_dict(self) -> dict[str, float | int]:
        return {
            "rows": self.rows,
            "page_load_ms": self.page_load_ms,
            "search_latency_ms": self.search_latency_ms,
            "filter_latency_ms": self.filter_latency_ms,
            "sort_latency_ms": self.sort_latency_ms,
        }


def _measure_ms(fn: Callable[[], None], *, iterations: int = 7) -> float:
    samples: list[float] = []
    for _ in range(max(3, iterations)):
        started = perf_counter()
        fn()
        elapsed = (perf_counter() - started) * 1000.0
        samples.append(elapsed)
    return round(median(samples), 3)


def _generate_dataset(rows: int) -> dict[str, list[dict[str, object]]]:
    page_rows: list[dict[str, object]] = []
    email_rows: list[dict[str, object]] = []
    document_rows: list[dict[str, object]] = []
    intel_rows: list[dict[str, object]] = []

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
        and any(t in types for t in list(row.get("finding_types", [])))
        and from_ts <= int(row.get("timestamp_ms", 0)) <= to_ts
    ]

    _ = [
        row
        for row in dataset["email_rows"]
        if row.get("seed") == seed and row.get("domain") == domain and from_ts <= int(row.get("timestamp_ms", 0)) <= to_ts
    ]

    _ = [
        row
        for row in dataset["document_rows"]
        if row.get("seed") == seed and row.get("domain") == domain and from_ts <= int(row.get("timestamp_ms", 0)) <= to_ts
    ]

    _ = [
        row
        for row in dataset["intelligence_rows"]
        if row.get("seed") == seed
        and row.get("domain") == domain
        and row.get("type") in types
        and from_ts <= int(row.get("timestamp_ms", 0)) <= to_ts
    ]


def _sort_operation(dataset: dict[str, list[dict[str, object]]]) -> None:
    _ = sorted(dataset["page_rows"], key=lambda row: (str(row.get("title", "")), int(row.get("timestamp_ms", 0))))
    _ = sorted(dataset["email_rows"], key=lambda row: str(row.get("value", "")))
    _ = sorted(dataset["document_rows"], key=lambda row: str(row.get("value", "")))
    _ = sorted(dataset["intelligence_rows"], key=lambda row: (str(row.get("type", "")), int(row.get("timestamp_ms", 0))))


def benchmark_dashboard_dataset(rows: int, *, iterations: int = 7) -> DashboardBenchmarkResult:
    dataset = _generate_dataset(rows)

    result = DashboardBenchmarkResult(
        rows=rows,
        page_load_ms=_measure_ms(lambda: _page_load_operation(dataset), iterations=iterations),
        search_latency_ms=_measure_ms(lambda: _search_operation(dataset, "site1 user1"), iterations=iterations),
        filter_latency_ms=_measure_ms(lambda: _filter_operation(dataset), iterations=iterations),
        sort_latency_ms=_measure_ms(lambda: _sort_operation(dataset), iterations=iterations),
    )

    return result


def run_dashboard_benchmarks(*, sizes: list[int] | None = None, iterations: int = 7) -> list[DashboardBenchmarkResult]:
    targets = sizes or [1000, 5000, 10000]
    return [benchmark_dashboard_dataset(size, iterations=iterations) for size in targets]


def has_regression(results: list[DashboardBenchmarkResult], *, threshold_ms: float = THRESHOLD_MS) -> list[str]:
    failures: list[str] = []
    for row in results:
        payload = row.as_dict()
        for metric in ("page_load_ms", "search_latency_ms", "filter_latency_ms", "sort_latency_ms"):
            value = float(payload[metric])
            if value > threshold_ms:
                failures.append(f"rows={row.rows} metric={metric} value={value:.3f}ms threshold={threshold_ms:.3f}ms")
    return failures
