from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .crawler import CrawlResult


def read_seed_urls(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    urls: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue

        if "," in raw:
            first_col = raw.split(",", 1)[0].strip()
            if first_col and first_col.lower() != "url":
                urls.append(first_col)
            continue

        urls.append(raw)

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)

    return deduped


def write_emails_txt(results: Iterable[CrawlResult], output_path: str) -> int:
    all_emails = sorted({email for result in results for email in result.emails})
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(all_emails), encoding="utf-8")
    return len(all_emails)


def write_results_json(results: Iterable[CrawlResult], output_path: str) -> None:
    payload = [result.to_dict() for result in results]
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_snapshot_diff_json(snapshot_diff: dict, output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot_diff or {}, indent=2), encoding="utf-8")


def write_results_csv(results: Iterable[CrawlResult], output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "seed_url",
                "page_url",
                "title",
                "description",
                "keywords",
                "emails",
                "phones",
                "documents",
                "images",
                "javascript_assets",
                "technologies",
                "security_headers_count",
                "broken_links",
                "social_accounts",
                "intelligence_findings",
                "internal_links",
                "external_links",
            ],
        )
        writer.writeheader()

        for result in results:
            for finding in result.page_findings:
                writer.writerow(
                    {
                        "seed_url": result.seed_url,
                        "page_url": finding.url,
                        "title": finding.title,
                        "description": finding.description,
                        "keywords": ";".join(sorted(finding.keywords)),
                        "emails": ";".join(sorted(finding.emails)),
                        "phones": ";".join(sorted(finding.phones)),
                        "documents": ";".join(sorted(finding.documents)),
                        "images": ";".join(sorted(finding.images)),
                        "javascript_assets": ";".join(sorted(finding.javascript_assets)),
                        "technologies": ";".join(sorted(finding.technologies)),
                        "security_headers_count": len(finding.security_headers),
                        "broken_links": ";".join(sorted(finding.broken_links)),
                        "social_accounts": ";".join(sorted(finding.social_accounts)),
                        "intelligence_findings": len(result.intelligence_findings),
                        "internal_links": len(finding.internal_links),
                        "external_links": len(finding.external_links),
                    }
                )


def write_stats_json(
    results: Iterable[CrawlResult],
    output_path: str,
    *,
    snapshot_diff: dict | None = None,
) -> dict:
    items = list(results)

    total_perf = {
        "queue_max_size": max((r.performance.queue_max_size for r in items), default=0),
        "fetch_time_seconds": round(sum(r.performance.fetch_time_seconds for r in items), 4),
        "robots_time_seconds": round(sum(r.performance.robots_time_seconds for r in items), 4),
        "extraction_time_seconds": round(sum(r.performance.extraction_time_seconds for r in items), 4),
        "soup_parse_time_seconds": round(sum(r.performance.soup_parse_time_seconds for r in items), 4),
        "broken_link_check_time_seconds": round(
            sum(r.performance.broken_link_check_time_seconds for r in items),
            4,
        ),
        "intelligence_collection_time_seconds": round(
            sum(r.performance.intelligence_collection_time_seconds for r in items),
            4,
        ),
        "rate_limit_wait_seconds": round(sum(r.performance.rate_limit_wait_seconds for r in items), 4),
        "bytes_downloaded": sum(r.performance.bytes_downloaded for r in items),
        "responses_non_html": sum(r.performance.responses_non_html for r in items),
        "responses_error_status": sum(r.performance.responses_error_status for r in items),
        "requests_completed": sum(r.performance.requests_completed for r in items),
    }
    total_perf["avg_fetch_time_ms"] = round(
        (float(total_perf["fetch_time_seconds"]) / max(1, int(total_perf["requests_completed"]))) * 1000.0,
        3,
    )
    total_perf["avg_bytes_per_response"] = round(
        int(total_perf["bytes_downloaded"]) / max(1, int(total_perf["requests_completed"])),
        3,
    )

    per_seed_perf = [
        {
            "seed_url": result.seed_url,
            "duration_seconds": round(result.duration_seconds, 3),
            **result.performance.to_dict(),
        }
        for result in items
    ]

    stats = {
        "seeds_processed": len(items),
        "pages_crawled": sum(r.pages_crawled for r in items),
        "visited_urls": sum(len(r.visited_urls) for r in items),
        "discovered_links": sum(len(r.discovered_links) for r in items),
        "intelligence_findings": sum(len(r.intelligence_findings) for r in items),
        "titles_captured": sum(
            1 for result in items for finding in result.page_findings if finding.title
        ),
        "unique_emails": len({email for result in items for email in result.emails}),
        "unique_phones": len({phone for result in items for phone in result.phones}),
        "unique_documents": len({doc for result in items for doc in result.documents}),
        "unique_images": len({img for result in items for img in result.images}),
        "unique_javascript_assets": len(
            {
                asset
                for result in items
                for finding in result.page_findings
                for asset in finding.javascript_assets
            }
        ),
        "unique_technologies": len(
            {
                tech
                for result in items
                for finding in result.page_findings
                for tech in finding.technologies
            }
        ),
        "broken_links": sum(len(finding.broken_links) for result in items for finding in result.page_findings),
        "unique_social_accounts": len({acct for result in items for acct in result.social_accounts}),
        "errors": sum(len(r.errors) for r in items),
        "requests_attempted": sum(r.requests_attempted for r in items),
        "retries": sum(r.retries for r in items),
        "duplicate_pages": sum(r.duplicate_pages for r in items),
        "blocked_by_robots": sum(r.blocked_by_robots for r in items),
        "blocked_by_domain": sum(r.blocked_by_domain for r in items),
        "links_dropped_by_cap": sum(r.links_dropped_by_cap for r in items),
        "unchanged_pages_skipped": sum(r.unchanged_pages_skipped for r in items),
        "non_html_skipped": sum(r.non_html_skipped for r in items),
        "duration_seconds": round(sum(r.duration_seconds for r in items), 3),
        "performance": {
            "aggregate": total_perf,
            "per_seed": per_seed_perf,
        },
    }

    if snapshot_diff:
        stats["snapshot_diff"] = snapshot_diff

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats
