from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

import yaml

from .crawler import AsyncOsintCrawler, CrawlConfig
from .io_utils import (
    read_seed_urls,
    write_emails_txt,
    write_results_csv,
    write_results_json,
    write_snapshot_diff_json,
    write_stats_json,
)
from .reporting import write_html_report
from .storage import (
    compare_run_with_previous,
    load_latest_links_by_source,
    load_latest_page_hashes,
    persist_results_sqlite,
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, sort_keys=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="email-crawler",
        description="Authorized OSINT crawler for asset discovery.",
    )

    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--seeds",
        default="data/seeds.txt",
        help="Path to text or simple CSV file containing seed URLs (default: data/seeds.txt)",
    )
    parser.add_argument("--max-pages", type=int, default=100, help="Max pages per seed URL")
    parser.add_argument("--max-depth", type=int, default=2, help="Link depth from each seed URL")
    parser.add_argument("--concurrency", type=int, default=20, help="Max concurrent HTTP requests")
    parser.add_argument(
        "--thread-pool-workers",
        type=int,
        default=0,
        help="Thread pool workers for HTML parsing/extractor tasks (0 disables thread pool)",
    )
    parser.add_argument("--timeout", type=float, default=12.0, help="Request timeout in seconds")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between requests in seconds")
    parser.add_argument("--retries", type=int, default=1, help="Retries per request")
    parser.add_argument(
        "--retry-statuses",
        default="429,500,502,503,504",
        help="Comma-separated HTTP statuses that should be retried",
    )
    parser.add_argument(
        "--retry-backoff-base",
        type=float,
        default=0.5,
        help="Exponential backoff base delay in seconds",
    )
    parser.add_argument(
        "--retry-backoff-max",
        type=float,
        default=8.0,
        help="Maximum exponential backoff delay in seconds",
    )
    parser.add_argument(
        "--user-agent",
        default="EmailCrawlerBot/1.0 (+https://example.local)",
        help="HTTP User-Agent header for requests",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.0,
        help="Max requests per second per host (0 disables rate limiting)",
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Disable robots.txt checks (not recommended)",
    )
    parser.add_argument(
        "--no-collect-robots",
        action="store_true",
        help="Disable robots.txt intelligence collector",
    )
    parser.add_argument(
        "--no-collect-sitemap",
        action="store_true",
        help="Disable sitemap.xml intelligence collector",
    )
    parser.add_argument(
        "--no-collect-security",
        action="store_true",
        help="Disable security.txt intelligence collector",
    )
    parser.add_argument(
        "--no-collect-feeds",
        action="store_true",
        help="Disable RSS/Atom feed intelligence collector",
    )
    parser.add_argument(
        "--no-collect-contact-pages",
        action="store_true",
        help="Disable common contact page intelligence collector",
    )
    parser.add_argument(
        "--no-collect-whois",
        action="store_true",
        help="Disable WHOIS/RDAP intelligence collector",
    )
    parser.add_argument(
        "--no-collect-tls",
        action="store_true",
        help="Disable TLS certificate intelligence collector",
    )
    parser.add_argument(
        "--no-collect-security-headers",
        action="store_true",
        help="Disable HTTP security headers collector",
    )
    parser.add_argument(
        "--no-collect-tech-fingerprint",
        action="store_true",
        help="Disable technology fingerprinting collector",
    )
    parser.add_argument(
        "--no-collect-javascript-assets",
        action="store_true",
        help="Disable JavaScript asset inventory extraction",
    )
    parser.add_argument(
        "--no-collect-subdomains",
        action="store_true",
        help="Disable passive subdomain enumeration",
    )
    parser.add_argument(
        "--collect-screenshots",
        action="store_true",
        help="Capture screenshots for seed URLs (requires playwright)",
    )
    parser.add_argument(
        "--screenshot-dir",
        default="output/screenshots",
        help="Directory where screenshots are saved",
    )
    parser.add_argument(
        "--no-collect-broken-links",
        action="store_true",
        help="Disable broken-link validation during crawl",
    )
    parser.add_argument(
        "--broken-links-max-checks-per-page",
        type=int,
        default=40,
        help="Maximum links to validate per page for broken-link checks",
    )
    parser.add_argument(
        "--broken-links-include-external",
        action="store_true",
        help="Check external links for broken-link detection as well",
    )
    parser.add_argument(
        "--max-links-per-page-saved",
        type=int,
        default=200,
        help="Cap number of discovered links saved per page in JSON results",
    )
    parser.add_argument(
        "--max-discovered-links-per-seed",
        type=int,
        default=10000,
        help="Hard cap on total discovered links tracked per seed",
    )
    parser.add_argument(
        "--checkpoint-dir",
        default="output/checkpoints",
        help="Directory for checkpoint files",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume unfinished crawls from checkpoint files",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Enable incremental crawling using previous run content hashes",
    )
    parser.add_argument(
        "--checkpoint-every-pages",
        type=int,
        default=10,
        help="Persist checkpoint every N crawled pages",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        default="",
        help="Optional file path for JSON logs",
    )

    parser.add_argument(
        "--cross-domain",
        action="store_true",
        help="Allow crawling links outside the seed domain",
    )
    parser.add_argument(
        "--allow-domain",
        action="append",
        default=[],
        help="Domain allowlist entry (repeatable). Example: --allow-domain example.com",
    )
    parser.add_argument("--out-emails", default="output/emails.txt", help="Output txt for unique emails")
    parser.add_argument("--out-json", default="output/results.json", help="Output json for detailed crawl results")
    parser.add_argument("--out-csv", default="output/results.csv", help="Output csv summary for each seed")
    parser.add_argument("--out-stats", default="output/stats.json", help="Output aggregated crawl stats json")
    parser.add_argument(
        "--out-snapshot-diff",
        default="output/snapshot_diff.json",
        help="Output snapshot comparison json",
    )
    parser.add_argument("--out-sqlite", default="output/findings.db", help="Output sqlite database path")
    parser.add_argument("--out-html", default="output/report.html", help="Output HTML report path")

    return parser


async def run(args: argparse.Namespace) -> int:
    seeds = read_seed_urls(args.seeds)
    if not seeds:
        raise ValueError(f"No seed URLs found in {args.seeds}")

    retry_statuses = tuple(
        int(item.strip())
        for item in args.retry_statuses.split(",")
        if item.strip().isdigit()
    )
    if not retry_statuses:
        retry_statuses = (429, 500, 502, 503, 504)

    allowlist = tuple(item.strip().lower() for item in args.allow_domain if item.strip())
    if not allowlist and not args.cross_domain:
        # If no explicit allowlist is provided, use seed domains.
        from urllib.parse import urlsplit

        allowlist = tuple(
            sorted(
                {
                    (urlsplit(seed).hostname or "").lower()
                    for seed in seeds
                    if (urlsplit(seed).hostname or "")
                }
            )
        )

    config = CrawlConfig(
        max_pages_per_seed=args.max_pages,
        max_depth=args.max_depth,
        concurrency=args.concurrency,
        thread_pool_workers=max(0, args.thread_pool_workers),
        timeout_seconds=args.timeout,
        delay_seconds=args.delay,
        max_retries=args.retries,
        retry_statuses=retry_statuses,
        retry_backoff_base=args.retry_backoff_base,
        retry_backoff_max=args.retry_backoff_max,
        user_agent=args.user_agent,
        rate_limit_per_second=args.rate_limit,
        obey_robots_txt=not args.ignore_robots,
        collect_robots=not args.no_collect_robots,
        collect_sitemap=not args.no_collect_sitemap,
        collect_security_txt=not args.no_collect_security,
        collect_feeds=not args.no_collect_feeds,
        collect_contact_pages=not args.no_collect_contact_pages,
        collect_whois=not args.no_collect_whois,
        collect_tls=not args.no_collect_tls,
        collect_security_headers=not args.no_collect_security_headers,
        collect_tech_fingerprint=not args.no_collect_tech_fingerprint,
        collect_javascript_assets=not args.no_collect_javascript_assets,
        collect_subdomains=not args.no_collect_subdomains,
        collect_screenshots=bool(args.collect_screenshots),
        screenshot_dir=args.screenshot_dir,
        collect_broken_links=not args.no_collect_broken_links,
        broken_links_max_checks_per_page=max(1, args.broken_links_max_checks_per_page),
        broken_links_same_domain_only=not args.broken_links_include_external,
        max_links_per_page_saved=max(1, args.max_links_per_page_saved),
        max_discovered_links_per_seed=max(1, args.max_discovered_links_per_seed),
        checkpoint_dir=args.checkpoint_dir,
        resume=args.resume,
        checkpoint_every_pages=max(1, args.checkpoint_every_pages),
        allowed_domains=allowlist if not args.cross_domain else (),
        incremental_crawl=bool(args.incremental),
    )

    if config.incremental_crawl:
        config.previous_content_hashes = load_latest_page_hashes(args.out_sqlite)
        config.previous_links_by_source = load_latest_links_by_source(args.out_sqlite)

    crawler = AsyncOsintCrawler(config)
    results = await crawler.crawl_many(seeds)

    total_emails = write_emails_txt(results, args.out_emails)
    write_results_json(results, args.out_json)
    write_results_csv(results, args.out_csv)
    persist_config_payload = {
        "max_pages": args.max_pages,
        "max_depth": args.max_depth,
        "concurrency": args.concurrency,
        "allow_domain": sorted(list(allowlist)),
        "cross_domain": bool(args.cross_domain),
        "incremental": bool(args.incremental),
    }
    run_id = persist_results_sqlite(
        results,
        args.out_sqlite,
        config_payload=persist_config_payload,
        crawler_version="0.2.0",
    )
    snapshot_diff = compare_run_with_previous(args.out_sqlite, run_id)
    write_snapshot_diff_json(snapshot_diff, args.out_snapshot_diff)
    stats = write_stats_json(results, args.out_stats, snapshot_diff=snapshot_diff)
    write_html_report(results, stats, args.out_html)

    print("=== Crawl Complete ===")
    print(f"Seeds processed : {stats['seeds_processed']}")
    print(f"Pages crawled   : {stats['pages_crawled']}")
    print(f"Links found     : {stats['discovered_links']}")
    print(f"Titles captured : {stats['titles_captured']}")
    print(f"Unique emails   : {total_emails}")
    print(f"Errors logged   : {stats['errors']}")
    print(f"Retries used    : {stats['retries']}")
    print(f"Dup pages skip  : {stats['duplicate_pages']}")
    print(f"Unchanged skip  : {stats['unchanged_pages_skipped']}")
    print(f"Robots blocked  : {stats['blocked_by_robots']}")
    print(f"Links dropped   : {stats['links_dropped_by_cap']}")
    if snapshot_diff.get("previous_run_id"):
        print(
            "Snapshot diff  : "
            f"new_pages={snapshot_diff['new_pages']} "
            f"changed_pages={snapshot_diff['changed_pages']} "
            f"removed_pages={snapshot_diff['removed_pages']} "
            f"new_findings={snapshot_diff['new_findings']} "
            f"removed_findings={snapshot_diff['removed_findings']}"
        )
    print(f"Emails output   : {Path(args.out_emails).resolve()}")
    print(f"JSON output     : {Path(args.out_json).resolve()}")
    print(f"CSV output      : {Path(args.out_csv).resolve()}")
    print(f"Stats output    : {Path(args.out_stats).resolve()}")
    print(f"Snapshot diff   : {Path(args.out_snapshot_diff).resolve()}")
    print(f"SQLite output   : {Path(args.out_sqlite).resolve()} (run_id={run_id})")
    print(f"HTML report     : {Path(args.out_html).resolve()}")

    return 0


def main() -> int:
    parser = build_parser()
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", default="config.yaml")
    pre_args, _ = config_parser.parse_known_args()

    file_defaults = _load_yaml_defaults(pre_args.config)
    if file_defaults:
        parser.set_defaults(**file_defaults)

    args = parser.parse_args()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)

    if args.log_file:
        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(JsonLogFormatter())
        root.addHandler(file_handler)

    root.setLevel(getattr(logging, args.log_level))
    return asyncio.run(run(args))


def _load_yaml_defaults(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        return {}

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}

    defaults = dict(data)

    # YAML uses positive booleans for collectors; CLI uses negative flags.
    if "collect_robots" in defaults:
        defaults["no_collect_robots"] = not bool(defaults.pop("collect_robots"))
    if "collect_sitemap" in defaults:
        defaults["no_collect_sitemap"] = not bool(defaults.pop("collect_sitemap"))
    if "collect_security_txt" in defaults:
        defaults["no_collect_security"] = not bool(defaults.pop("collect_security_txt"))
    if "collect_feeds" in defaults:
        defaults["no_collect_feeds"] = not bool(defaults.pop("collect_feeds"))
    if "collect_contact_pages" in defaults:
        defaults["no_collect_contact_pages"] = not bool(defaults.pop("collect_contact_pages"))
    if "collect_whois" in defaults:
        defaults["no_collect_whois"] = not bool(defaults.pop("collect_whois"))
    if "collect_tls" in defaults:
        defaults["no_collect_tls"] = not bool(defaults.pop("collect_tls"))
    if "collect_security_headers" in defaults:
        defaults["no_collect_security_headers"] = not bool(defaults.pop("collect_security_headers"))
    if "collect_tech_fingerprint" in defaults:
        defaults["no_collect_tech_fingerprint"] = not bool(defaults.pop("collect_tech_fingerprint"))
    if "collect_javascript_assets" in defaults:
        defaults["no_collect_javascript_assets"] = not bool(defaults.pop("collect_javascript_assets"))
    if "collect_subdomains" in defaults:
        defaults["no_collect_subdomains"] = not bool(defaults.pop("collect_subdomains"))
    if "collect_broken_links" in defaults:
        defaults["no_collect_broken_links"] = not bool(defaults.pop("collect_broken_links"))

    if "broken_links_same_domain_only" in defaults:
        defaults["broken_links_include_external"] = not bool(
            defaults.pop("broken_links_same_domain_only")
        )

    return defaults


if __name__ == "__main__":
    raise SystemExit(main())
