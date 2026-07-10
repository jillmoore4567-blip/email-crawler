from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging
import posixpath
import random
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import aiohttp
from bs4 import BeautifulSoup

from .extractors import (
    DNSExtractor,
    build_default_extractors,
)
from .extractors.base import ExtractionContext
from .intelligence import IntelligenceCollector, IntelligenceFinding

logger = logging.getLogger(__name__)

TRACKING_QUERY_PREFIXES = (
    "utm_",
    "fbclid",
    "gclid",
    "mc_eid",
    "mc_cid",
    "ref",
    "source",
)


@dataclass(slots=True)
class CrawlConfig:
    max_pages_per_seed: int = 100
    max_depth: int = 2
    concurrency: int = 20
    thread_pool_workers: int = 0
    timeout_seconds: float = 12.0
    user_agent: str = "EmailCrawlerBot/1.0 (+https://example.local)"
    delay_seconds: float = 0.0
    rate_limit_per_second: float = 0.0
    max_retries: int = 2
    retry_backoff_base: float = 0.5
    retry_backoff_max: float = 8.0
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    obey_robots_txt: bool = True
    collect_robots: bool = True
    collect_sitemap: bool = True
    collect_security_txt: bool = True
    collect_feeds: bool = True
    collect_contact_pages: bool = True
    collect_whois: bool = False
    collect_tls: bool = False
    collect_security_headers: bool = True
    collect_tech_fingerprint: bool = True
    collect_javascript_assets: bool = True
    collect_subdomains: bool = False
    collect_screenshots: bool = False
    screenshot_dir: str = "output/screenshots"
    collect_broken_links: bool = False
    broken_links_max_checks_per_page: int = 40
    broken_links_same_domain_only: bool = True
    dedupe_content: bool = True
    max_links_per_page_saved: int = 200
    max_discovered_links_per_seed: int = 10000
    checkpoint_dir: str | None = None
    resume: bool = False
    checkpoint_every_pages: int = 10
    allowed_domains: tuple[str, ...] = ()
    incremental_crawl: bool = False
    previous_content_hashes: dict[str, str] = field(default_factory=dict)
    previous_links_by_source: dict[str, list[str]] = field(default_factory=dict)
    live_stream_path: str = ""


@dataclass(slots=True)
class PageFinding:
    url: str
    http_status: int = 200
    content_hash: str = ""
    title: str = ""
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_accounts: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    javascript_assets: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    security_headers: dict[str, str] = field(default_factory=dict)
    broken_links: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "http_status": self.http_status,
            "content_hash": self.content_hash,
            "title": self.title,
            "description": self.description,
            "keywords": self.keywords,
            "emails": self.emails,
            "phones": self.phones,
            "social_accounts": self.social_accounts,
            "documents": self.documents,
            "images": self.images,
            "javascript_assets": self.javascript_assets,
            "technologies": self.technologies,
            "security_headers": self.security_headers,
            "broken_links": self.broken_links,
            "links": self.links,
            "internal_links": self.internal_links,
            "external_links": self.external_links,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageFinding":
        return cls(
            url=data.get("url", ""),
            http_status=int(data.get("http_status", 200)),
            content_hash=data.get("content_hash", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            keywords=list(data.get("keywords", [])),
            emails=list(data.get("emails", [])),
            phones=list(data.get("phones", [])),
            social_accounts=list(data.get("social_accounts", [])),
            documents=list(data.get("documents", [])),
            images=list(data.get("images", [])),
            javascript_assets=list(data.get("javascript_assets", [])),
            technologies=list(data.get("technologies", [])),
            security_headers=dict(data.get("security_headers", {})),
            broken_links=list(data.get("broken_links", [])),
            links=list(data.get("links", [])),
            internal_links=list(data.get("internal_links", [])),
            external_links=list(data.get("external_links", [])),
        )


@dataclass(slots=True)
class CrawlResult:
    seed_url: str
    pages_crawled: int = 0
    visited_urls: set[str] = field(default_factory=set)
    discovered_links: set[str] = field(default_factory=set)
    page_findings: list[PageFinding] = field(default_factory=list)
    dns_records: list[str] = field(default_factory=list)
    intelligence_findings: list[IntelligenceFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requests_attempted: int = 0
    retries: int = 0
    duplicate_pages: int = 0
    blocked_by_robots: int = 0
    blocked_by_domain: int = 0
    non_html_skipped: int = 0
    links_dropped_by_cap: int = 0
    unchanged_pages_skipped: int = 0
    unchanged_urls: set[str] = field(default_factory=set)
    performance: "CrawlPerformanceMetrics" = field(default_factory=lambda: CrawlPerformanceMetrics())
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        end = self.finished_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    @property
    def emails(self) -> set[str]:
        return {e for finding in self.page_findings for e in finding.emails}

    @property
    def phones(self) -> set[str]:
        return {p for finding in self.page_findings for p in finding.phones}

    @property
    def documents(self) -> set[str]:
        return {d for finding in self.page_findings for d in finding.documents}

    @property
    def social_accounts(self) -> set[str]:
        return {s for finding in self.page_findings for s in finding.social_accounts}

    @property
    def images(self) -> set[str]:
        return {img for finding in self.page_findings for img in finding.images}

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed_url": self.seed_url,
            "pages_crawled": self.pages_crawled,
            "visited_urls": sorted(self.visited_urls),
            "discovered_links": sorted(self.discovered_links),
            "page_findings": [finding.to_dict() for finding in self.page_findings],
            "dns_records": self.dns_records,
            "intelligence_findings": [item.to_dict() for item in self.intelligence_findings],
            "errors": self.errors,
            "requests_attempted": self.requests_attempted,
            "retries": self.retries,
            "duplicate_pages": self.duplicate_pages,
            "blocked_by_robots": self.blocked_by_robots,
            "blocked_by_domain": self.blocked_by_domain,
            "non_html_skipped": self.non_html_skipped,
            "links_dropped_by_cap": self.links_dropped_by_cap,
            "unchanged_pages_skipped": self.unchanged_pages_skipped,
            "unchanged_urls": sorted(self.unchanged_urls),
            "performance": self.performance.to_dict(),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CrawlResult":
        started_at = data.get("started_at")
        finished_at = data.get("finished_at")
        return cls(
            seed_url=data["seed_url"],
            pages_crawled=int(data.get("pages_crawled", 0)),
            visited_urls=set(data.get("visited_urls", [])),
            discovered_links=set(data.get("discovered_links", [])),
            page_findings=[PageFinding.from_dict(item) for item in data.get("page_findings", [])],
            dns_records=list(data.get("dns_records", [])),
            intelligence_findings=[
                IntelligenceFinding.from_dict(item) for item in data.get("intelligence_findings", [])
            ],
            errors=list(data.get("errors", [])),
            requests_attempted=int(data.get("requests_attempted", 0)),
            retries=int(data.get("retries", 0)),
            duplicate_pages=int(data.get("duplicate_pages", 0)),
            blocked_by_robots=int(data.get("blocked_by_robots", 0)),
            blocked_by_domain=int(data.get("blocked_by_domain", 0)),
            non_html_skipped=int(data.get("non_html_skipped", 0)),
            links_dropped_by_cap=int(data.get("links_dropped_by_cap", 0)),
            unchanged_pages_skipped=int(data.get("unchanged_pages_skipped", 0)),
            unchanged_urls=set(data.get("unchanged_urls", [])),
            performance=CrawlPerformanceMetrics.from_dict(data.get("performance", {})),
            started_at=datetime.fromisoformat(started_at) if started_at else datetime.now(timezone.utc),
            finished_at=datetime.fromisoformat(finished_at) if finished_at else None,
        )


@dataclass(slots=True)
class CrawlPerformanceMetrics:
    queue_max_size: int = 0
    fetch_time_seconds: float = 0.0
    robots_time_seconds: float = 0.0
    extraction_time_seconds: float = 0.0
    soup_parse_time_seconds: float = 0.0
    broken_link_check_time_seconds: float = 0.0
    intelligence_collection_time_seconds: float = 0.0
    rate_limit_wait_seconds: float = 0.0
    bytes_downloaded: int = 0
    responses_non_html: int = 0
    responses_error_status: int = 0
    requests_completed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_max_size": self.queue_max_size,
            "fetch_time_seconds": round(self.fetch_time_seconds, 4),
            "robots_time_seconds": round(self.robots_time_seconds, 4),
            "extraction_time_seconds": round(self.extraction_time_seconds, 4),
            "soup_parse_time_seconds": round(self.soup_parse_time_seconds, 4),
            "broken_link_check_time_seconds": round(self.broken_link_check_time_seconds, 4),
            "intelligence_collection_time_seconds": round(self.intelligence_collection_time_seconds, 4),
            "rate_limit_wait_seconds": round(self.rate_limit_wait_seconds, 4),
            "bytes_downloaded": self.bytes_downloaded,
            "responses_non_html": self.responses_non_html,
            "responses_error_status": self.responses_error_status,
            "requests_completed": self.requests_completed,
            "avg_fetch_time_ms": round((self.fetch_time_seconds / max(1, self.requests_completed)) * 1000.0, 3),
            "avg_bytes_per_response": round(self.bytes_downloaded / max(1, self.requests_completed), 3),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CrawlPerformanceMetrics":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            queue_max_size=int(payload.get("queue_max_size", 0) or 0),
            fetch_time_seconds=float(payload.get("fetch_time_seconds", 0.0) or 0.0),
            robots_time_seconds=float(payload.get("robots_time_seconds", 0.0) or 0.0),
            extraction_time_seconds=float(payload.get("extraction_time_seconds", 0.0) or 0.0),
            soup_parse_time_seconds=float(payload.get("soup_parse_time_seconds", 0.0) or 0.0),
            broken_link_check_time_seconds=float(payload.get("broken_link_check_time_seconds", 0.0) or 0.0),
            intelligence_collection_time_seconds=float(
                payload.get("intelligence_collection_time_seconds", 0.0) or 0.0
            ),
            rate_limit_wait_seconds=float(payload.get("rate_limit_wait_seconds", 0.0) or 0.0),
            bytes_downloaded=int(payload.get("bytes_downloaded", 0) or 0),
            responses_non_html=int(payload.get("responses_non_html", 0) or 0),
            responses_error_status=int(payload.get("responses_error_status", 0) or 0),
            requests_completed=int(payload.get("requests_completed", 0) or 0),
        )


class AsyncRateLimiter:
    def __init__(self, rate_per_second: float):
        self._min_interval = (1.0 / rate_per_second) if rate_per_second > 0 else 0.0
        self._lock = asyncio.Lock()
        self._last_request_at: dict[str, float] = {}

    async def wait(self, host: str) -> float:
        if self._min_interval <= 0 or not host:
            return 0.0

        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            last = self._last_request_at.get(host, 0.0)
            wait_for = self._min_interval - (now - last)
            if wait_for > 0:
                await asyncio.sleep(wait_for)
                now = loop.time()
            self._last_request_at[host] = now
            return max(0.0, wait_for)


class AsyncOsintCrawler:
    def __init__(self, config: CrawlConfig):
        self.config = config
        self._sem = asyncio.Semaphore(config.concurrency)
        self._rate_limiter = AsyncRateLimiter(config.rate_limit_per_second)
        self._robots_lock = asyncio.Lock()
        self._robots_cache: dict[str, RobotFileParser | None] = {}
        self._executor: ThreadPoolExecutor | None = None
        self._dns_extractor = DNSExtractor()
        self._intel_collector = IntelligenceCollector(self._canonicalize_url)
        self._extractors = build_default_extractors(
            self._canonicalize_url,
            collect_javascript_assets=self.config.collect_javascript_assets,
        )
        self._stream_sequence = 0
        self._live_stream_file: Path | None = None
        if self.config.live_stream_path:
            self._live_stream_file = Path(self.config.live_stream_path)
            self._live_stream_file.parent.mkdir(parents=True, exist_ok=True)
            self._live_stream_file.write_text("", encoding="utf-8")

    async def crawl_many(self, seed_urls: Iterable[str]) -> list[CrawlResult]:
        seeds = list(seed_urls)
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        connector = aiohttp.TCPConnector(limit=max(10, self.config.concurrency * 2))
        headers = {"User-Agent": self.config.user_agent}

        if self.config.thread_pool_workers > 0:
            self._executor = ThreadPoolExecutor(max_workers=self.config.thread_pool_workers)

        self._emit_live_event(
            "crawl_started",
            seed_count=len(seeds),
            concurrency=self.config.concurrency,
            max_depth=self.config.max_depth,
            max_pages_per_seed=self.config.max_pages_per_seed,
        )

        try:
            async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers) as session:
                tasks = [self._crawl_seed(session, self._canonicalize_url(seed)) for seed in seeds]
                results = await asyncio.gather(*tasks)
        finally:
            if self._executor is not None:
                self._executor.shutdown(wait=True)
                self._executor = None

        self._log_struct(
            "crawl_finished",
            seeds=len(results),
            pages=sum(r.pages_crawled for r in results),
            unique_emails=len({email for result in results for email in result.emails}),
            errors=sum(len(r.errors) for r in results),
            retries=sum(r.retries for r in results),
            duplicates=sum(r.duplicate_pages for r in results),
        )
        self._emit_live_event(
            "crawl_completed",
            seeds=len(results),
            pages=sum(r.pages_crawled for r in results),
            errors=sum(len(r.errors) for r in results),
            retries=sum(r.retries for r in results),
        )
        return results

    async def _crawl_seed(self, session: aiohttp.ClientSession, seed_url: str) -> CrawlResult:
        checkpoint_state = self._load_checkpoint(seed_url) if self.config.resume else None
        queue: deque[tuple[str, int]]
        seen: set[str]
        enqueued: set[str]
        content_hashes: set[str]
        result: CrawlResult
        if checkpoint_state:
            queue = deque((item[0], int(item[1])) for item in checkpoint_state.get("queue", []))
            seen = set(checkpoint_state.get("seen", []))
            enqueued = {url for url, _depth in queue}
            content_hashes = set(checkpoint_state.get("content_hashes", []))
            result = CrawlResult.from_dict(checkpoint_state.get("result", {"seed_url": seed_url}))
            self._log_struct("checkpoint_loaded", seed=seed_url, pending=len(queue), seen=len(seen))
        else:
            queue = deque([(seed_url, 0)])
            seen = set()
            enqueued = {seed_url}
            content_hashes = set()
            result = CrawlResult(seed_url=seed_url)
            result.dns_records = self._dns_extractor.resolve_host(seed_url)
        self._emit_live_event(
            "seed_started",
            seed=seed_url,
            queue_depth=len(queue),
            pages_crawled=result.pages_crawled,
        )
        result.performance.queue_max_size = max(result.performance.queue_max_size, len(queue))

        seed_host = (urlsplit(seed_url).hostname or "").lower()

        async def _can_fetch_with_metrics(target_url: str) -> bool:
            robots_started = perf_counter()
            allowed = await self._allowed_by_robots(session, target_url)
            result.performance.robots_time_seconds += perf_counter() - robots_started
            return allowed

        intel_started = perf_counter()
        result.intelligence_findings = await self._intel_collector.collect(
            session,
            seed_url,
            can_fetch=_can_fetch_with_metrics,
            obey_robots=self.config.obey_robots_txt,
            collect_robots=self.config.collect_robots,
            collect_sitemap=self.config.collect_sitemap,
            collect_security_txt=self.config.collect_security_txt,
            collect_feeds=self.config.collect_feeds,
            collect_contact_pages=self.config.collect_contact_pages,
            collect_whois=self.config.collect_whois,
            collect_tls=self.config.collect_tls,
            collect_security_headers=self.config.collect_security_headers,
            collect_tech_fingerprint=self.config.collect_tech_fingerprint,
            collect_subdomains=self.config.collect_subdomains,
            collect_screenshots=self.config.collect_screenshots,
            screenshot_dir=self.config.screenshot_dir,
        )
        result.performance.intelligence_collection_time_seconds += perf_counter() - intel_started

        while queue and result.pages_crawled < self.config.max_pages_per_seed:
            current_url, depth = queue.popleft()
            enqueued.discard(current_url)

            if current_url in seen:
                continue
            seen.add(current_url)

            if not self._is_allowed_domain(current_url, seed_host):
                result.blocked_by_domain += 1
                continue

            if self.config.obey_robots_txt:
                robots_started = perf_counter()
                allowed_by_robots = await self._allowed_by_robots(session, current_url)
                result.performance.robots_time_seconds += perf_counter() - robots_started
                if not allowed_by_robots:
                    result.blocked_by_robots += 1
                    continue

            html, error, non_html, headers, fetch_metrics = await self._fetch_html(session, current_url, result)
            result.performance.fetch_time_seconds += float(fetch_metrics["fetch_seconds"])
            result.performance.rate_limit_wait_seconds += float(fetch_metrics["wait_seconds"])
            result.performance.bytes_downloaded += int(fetch_metrics["response_bytes"])
            result.performance.requests_completed += int(fetch_metrics["requests_completed"])
            result.performance.responses_non_html += int(fetch_metrics["responses_non_html"])
            result.performance.responses_error_status += int(fetch_metrics["responses_error_status"])
            result.visited_urls.add(current_url)

            if non_html:
                self._emit_live_event(
                    "non_html_skipped",
                    seed=seed_url,
                    url=current_url,
                    queue_depth=len(queue),
                )
                result.non_html_skipped += 1
                continue
            if error:
                self._emit_live_event(
                    "request_error",
                    seed=seed_url,
                    url=current_url,
                    error=error,
                    queue_depth=len(queue),
                )
                result.errors.append(error)
                continue
            if not html:
                continue

            content_hash = self._content_hash(html)

            if self.config.incremental_crawl:
                previous_hash = self.config.previous_content_hashes.get(current_url)
                if previous_hash and previous_hash == content_hash:
                    result.unchanged_pages_skipped += 1
                    result.unchanged_urls.add(current_url)
                    cached_links = self.config.previous_links_by_source.get(current_url, [])
                    for link in cached_links:
                        if link in result.discovered_links:
                            continue
                        if len(result.discovered_links) >= self.config.max_discovered_links_per_seed:
                            result.links_dropped_by_cap += 1
                            continue
                        result.discovered_links.add(link)
                        if depth < self.config.max_depth and link not in seen and link not in enqueued:
                            queue.append((link, depth + 1))
                            enqueued.add(link)
                    result.performance.queue_max_size = max(result.performance.queue_max_size, len(queue))
                    self._emit_live_event(
                        "page_unchanged",
                        seed=seed_url,
                        url=current_url,
                        queue_depth=len(queue),
                        pages_crawled=result.pages_crawled,
                    )
                    continue

            if self.config.dedupe_content and content_hash in content_hashes:
                result.duplicate_pages += 1
                self._emit_live_event(
                    "duplicate_page_skipped",
                    seed=seed_url,
                    url=current_url,
                    queue_depth=len(queue),
                )
                continue
            content_hashes.add(content_hash)

            extract_started = perf_counter()
            if self._executor is not None:
                loop = asyncio.get_running_loop()
                finding, parse_seconds = await loop.run_in_executor(
                    self._executor,
                    self._extract_page_finding_with_metrics,
                    current_url,
                    html,
                    seed_host,
                )
            else:
                finding, parse_seconds = self._extract_page_finding_with_metrics(current_url, html, seed_host)
            result.performance.soup_parse_time_seconds += parse_seconds
            result.performance.extraction_time_seconds += perf_counter() - extract_started

            finding.content_hash = content_hash

            if self.config.collect_security_headers:
                finding.security_headers = self._extract_security_headers(headers)
            if self.config.collect_tech_fingerprint:
                finding.technologies = self._fingerprint_technologies(html, headers)
            if self.config.collect_broken_links and finding.links:
                broken_started = perf_counter()
                broken = await self._detect_broken_links(session, current_url, finding.links, seed_host, result)
                result.performance.broken_link_check_time_seconds += perf_counter() - broken_started
                finding.broken_links = broken

            result.page_findings.append(finding)
            result.pages_crawled += 1
            self._emit_live_event(
                "page_crawled",
                seed=seed_url,
                url=current_url,
                depth=depth,
                status=finding.http_status,
                queue_depth=len(queue),
                pages_crawled=result.pages_crawled,
                links_found=len(finding.links),
                emails_found=len(finding.emails),
                documents_found=len(finding.documents),
            )

            for link in finding.links:
                if link in result.discovered_links:
                    continue
                if len(result.discovered_links) >= self.config.max_discovered_links_per_seed:
                    result.links_dropped_by_cap += 1
                    continue

                result.discovered_links.add(link)
                if depth < self.config.max_depth and link not in seen and link not in enqueued:
                    queue.append((link, depth + 1))
                    enqueued.add(link)

            result.performance.queue_max_size = max(result.performance.queue_max_size, len(queue))

            if self.config.checkpoint_dir and result.pages_crawled % max(1, self.config.checkpoint_every_pages) == 0:
                self._save_checkpoint(seed_url, queue, seen, content_hashes, result, complete=False)

        result.finished_at = datetime.now(timezone.utc)
        if self.config.checkpoint_dir:
            complete = len(queue) == 0
            self._save_checkpoint(seed_url, queue, seen, content_hashes, result, complete=complete)

        self._log_struct(
            "seed_crawl_complete",
            seed=result.seed_url,
            pages=result.pages_crawled,
            emails=len(result.emails),
            phones=len(result.phones),
            docs=len(result.documents),
            images=len(result.images),
            social=len(result.social_accounts),
            intelligence=len(result.intelligence_findings),
            links=len(result.discovered_links),
            errors=len(result.errors),
            retries=result.retries,
            blocked_by_robots=result.blocked_by_robots,
            blocked_by_domain=result.blocked_by_domain,
            duplicates=result.duplicate_pages,
            dropped_links=result.links_dropped_by_cap,
            fetch_time_seconds=round(result.performance.fetch_time_seconds, 3),
            extraction_time_seconds=round(result.performance.extraction_time_seconds, 3),
            robots_time_seconds=round(result.performance.robots_time_seconds, 3),
            rate_limit_wait_seconds=round(result.performance.rate_limit_wait_seconds, 3),
            duration_seconds=round(result.duration_seconds, 2),
        )
        self._emit_live_event(
            "seed_completed",
            seed=result.seed_url,
            pages=result.pages_crawled,
            errors=len(result.errors),
            retries=result.retries,
            duration_seconds=round(result.duration_seconds, 3),
        )
        return result

    def _extract_page_finding(self, page_url: str, html: str, seed_host: str) -> PageFinding:
        finding, _parse_seconds = self._extract_page_finding_with_metrics(page_url, html, seed_host)
        return finding

    def _extract_page_finding_with_metrics(
        self,
        page_url: str,
        html: str,
        seed_host: str,
    ) -> tuple[PageFinding, float]:
        parse_started = perf_counter()
        soup = BeautifulSoup(html, "html.parser")
        parse_seconds = perf_counter() - parse_started
        context = ExtractionContext(seed_host=seed_host)
        payload: dict[str, Any] = {"url": page_url}

        for extractor in self._extractors:
            data = extractor.extract(page_url, soup, context=context)
            payload.update(data)

        links = list(payload.get("links", []))
        if len(links) > self.config.max_links_per_page_saved:
            payload["links"] = links[: self.config.max_links_per_page_saved]

        return PageFinding.from_dict(payload), parse_seconds

    async def _fetch_html(
        self,
        session: aiohttp.ClientSession,
        url: str,
        result: CrawlResult,
    ) -> tuple[str | None, str | None, bool, dict[str, str], dict[str, float | int]]:
        last_error: str | None = None
        metrics: dict[str, float | int] = {
            "fetch_seconds": 0.0,
            "wait_seconds": 0.0,
            "response_bytes": 0,
            "requests_completed": 0,
            "responses_non_html": 0,
            "responses_error_status": 0,
        }

        for attempt in range(self.config.max_retries + 1):
            host = urlsplit(url).hostname or ""
            wait_s = await self._rate_limiter.wait(host)
            metrics["wait_seconds"] = float(metrics["wait_seconds"]) + wait_s
            if self.config.delay_seconds > 0:
                await asyncio.sleep(self.config.delay_seconds)
                metrics["wait_seconds"] = float(metrics["wait_seconds"]) + self.config.delay_seconds

            try:
                async with self._sem:
                    result.requests_attempted += 1
                    started = perf_counter()
                    async with session.get(url, allow_redirects=True) as response:
                        metrics["fetch_seconds"] = float(metrics["fetch_seconds"]) + (perf_counter() - started)
                        metrics["requests_completed"] = int(metrics["requests_completed"]) + 1
                        status = response.status
                        if status in self.config.retry_statuses:
                            last_error = f"{url} -> HTTP {status}"
                            metrics["responses_error_status"] = int(metrics["responses_error_status"]) + 1
                            if attempt < self.config.max_retries:
                                result.retries += 1
                                await asyncio.sleep(self._backoff_seconds(attempt))
                                continue
                            return None, last_error, False, {}, metrics

                        if status >= 400:
                            metrics["responses_error_status"] = int(metrics["responses_error_status"]) + 1
                            return None, f"{url} -> HTTP {status}", False, {}, metrics

                        content_type = response.headers.get("Content-Type", "")
                        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                            metrics["responses_non_html"] = int(metrics["responses_non_html"]) + 1
                            return None, None, True, dict(response.headers), metrics

                        html = await response.text(errors="ignore")
                        metrics["response_bytes"] = int(metrics["response_bytes"]) + len(
                            html.encode("utf-8", errors="ignore")
                        )
                        return html, None, False, dict(response.headers), metrics
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = f"{url} -> {exc.__class__.__name__}: {exc}"
                if attempt < self.config.max_retries:
                    result.retries += 1
                    await asyncio.sleep(self._backoff_seconds(attempt))

        return None, last_error, False, {}, metrics

    async def _detect_broken_links(
        self,
        session: aiohttp.ClientSession,
        source_url: str,
        links: list[str],
        seed_host: str,
        result: CrawlResult,
    ) -> list[str]:
        checked = 0
        broken: list[str] = []
        for link in links:
            if checked >= max(1, self.config.broken_links_max_checks_per_page):
                break

            parsed = urlsplit(link)
            if parsed.scheme not in {"http", "https"}:
                continue

            target_host = (parsed.hostname or "").lower()
            if self.config.broken_links_same_domain_only:
                if not target_host or not (target_host == seed_host or target_host.endswith(f".{seed_host}")):
                    continue

            checked += 1
            is_broken, status = await self._is_link_broken(session, link)
            if is_broken:
                broken.append(link)
                result.intelligence_findings.append(
                    IntelligenceFinding(
                        finding_type="broken_link",
                        url=link,
                        status=status,
                        details={"source_url": source_url},
                    )
                )

        return sorted(set(broken))

    async def _is_link_broken(self, session: aiohttp.ClientSession, url: str) -> tuple[bool, str]:
        host = urlsplit(url).hostname or ""
        await self._rate_limiter.wait(host)
        if self.config.delay_seconds > 0:
            await asyncio.sleep(self.config.delay_seconds)

        try:
            async with self._sem:
                async with session.head(url, allow_redirects=True) as response:
                    if response.status >= 400:
                        if response.status in {405, 501}:
                            return await self._is_link_broken_get(session, url)
                        return True, f"http_{response.status}"
                    return False, "ok"
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return await self._is_link_broken_get(session, url)

    async def _is_link_broken_get(self, session: aiohttp.ClientSession, url: str) -> tuple[bool, str]:
        host = urlsplit(url).hostname or ""
        await self._rate_limiter.wait(host)
        if self.config.delay_seconds > 0:
            await asyncio.sleep(self.config.delay_seconds)

        try:
            async with self._sem:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status >= 400:
                        return True, f"http_{response.status}"
                    return False, "ok"
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            return True, exc.__class__.__name__.lower()

    def _extract_security_headers(self, headers: dict[str, str]) -> dict[str, str]:
        if not headers:
            return {}

        normalized = {k.lower(): v for k, v in headers.items()}
        wanted = [
            "strict-transport-security",
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy",
            "permissions-policy",
        ]
        return {name: normalized[name] for name in wanted if name in normalized}

    def _fingerprint_technologies(self, html: str, headers: dict[str, str]) -> list[str]:
        detected: set[str] = set()
        lowered = html.lower()
        hdr = {k.lower(): v.lower() for k, v in headers.items()}

        server = hdr.get("server", "")
        powered = hdr.get("x-powered-by", "")

        if "cloudflare" in server or "cf-ray" in hdr:
            detected.add("Cloudflare")
        if "nginx" in server:
            detected.add("Nginx")
        if "apache" in server:
            detected.add("Apache")
        if "iis" in server:
            detected.add("IIS")
        if "php" in powered:
            detected.add("PHP")
        if "express" in powered:
            detected.add("Express")

        signatures = {
            "WordPress": ["/wp-content/", "wp-json"],
            "Drupal": ["drupal-settings-json", "sites/default/files"],
            "Joomla": ["/media/system/js/", "joomla"],
            "Shopify": ["cdn.shopify.com", "shopify.theme"],
            "React": ["react-dom", "__next", "data-reactroot"],
            "Next.js": ["/_next/", "__next"],
            "Vue": ["data-v-", "vue.js"],
            "Angular": ["ng-version", "angular"],
            "jQuery": ["jquery", "window.jquery"],
            "Bootstrap": ["bootstrap.min.css", "bootstrap.min.js"],
        }

        for name, markers in signatures.items():
            if any(marker in lowered for marker in markers):
                detected.add(name)

        return sorted(detected)

    async def _allowed_by_robots(self, session: aiohttp.ClientSession, url: str) -> bool:
        parsed = urlsplit(url)
        netloc = parsed.netloc or ""
        if not netloc:
            return False

        parser = await self._get_robots_parser(session, parsed.scheme or "https", netloc)
        if parser is None:
            return True
        return parser.can_fetch(self.config.user_agent, url)

    async def _get_robots_parser(
        self,
        session: aiohttp.ClientSession,
        scheme: str,
        netloc: str,
    ) -> RobotFileParser | None:
        key = f"{scheme.lower()}://{netloc.lower()}"
        if key in self._robots_cache:
            return self._robots_cache[key]

        async with self._robots_lock:
            if key in self._robots_cache:
                return self._robots_cache[key]

            robots_url = f"{key}/robots.txt"
            parser: RobotFileParser | None = None
            try:
                async with self._sem:
                    async with session.get(robots_url, allow_redirects=True) as response:
                        if response.status >= 400:
                            self._robots_cache[key] = None
                            return None
                        text = await response.text(errors="ignore")

                parser = RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(text.splitlines())
            except (aiohttp.ClientError, asyncio.TimeoutError):
                parser = None

            self._robots_cache[key] = parser
            return parser

    def _is_allowed_domain(self, candidate_url: str, seed_host: str) -> bool:
        candidate_host = (urlsplit(candidate_url).hostname or "").lower()
        if not candidate_host or not seed_host:
            return False

        if self.config.allowed_domains:
            return any(
                candidate_host == dom or candidate_host.endswith(f".{dom}")
                for dom in self.config.allowed_domains
            )

        return candidate_host == seed_host or candidate_host.endswith(f".{seed_host}")

    def _canonicalize_url(self, url: str) -> str:
        parts = urlsplit(url.strip())
        scheme = parts.scheme.lower() if parts.scheme else "https"

        host = (parts.hostname or "").lower()
        port = parts.port
        if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
            netloc = f"{host}:{port}"
        else:
            netloc = host

        path = parts.path or "/"
        normalized_path = posixpath.normpath(path)
        if path.endswith("/") and not normalized_path.endswith("/"):
            normalized_path += "/"
        if not normalized_path.startswith("/"):
            normalized_path = "/" + normalized_path
        if normalized_path != "/" and normalized_path.endswith("/"):
            normalized_path = normalized_path.rstrip("/")

        query_pairs = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not any(k.lower().startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES)
        ]
        query_pairs.sort(key=lambda item: (item[0], item[1]))
        query = urlencode(query_pairs, doseq=True)

        return urlunsplit((scheme, netloc, normalized_path, query, ""))

    def _content_hash(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        text = " ".join(soup.get_text(" ", strip=True).split())
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    def _backoff_seconds(self, attempt: int) -> float:
        raw = self.config.retry_backoff_base * (2**attempt)
        capped = min(raw, self.config.retry_backoff_max)
        jitter = random.uniform(0.0, 0.2 * capped if capped > 0 else 0.0)
        return capped + jitter

    def _checkpoint_file_for_seed(self, seed_url: str) -> Path | None:
        if not self.config.checkpoint_dir:
            return None

        parts = urlsplit(seed_url)
        host = (parts.hostname or "seed").replace(".", "_")
        file_name = f"{host}.checkpoint.json"
        path = Path(self.config.checkpoint_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path / file_name

    def _save_checkpoint(
        self,
        seed_url: str,
        queue: deque[tuple[str, int]],
        seen: set[str],
        content_hashes: set[str],
        result: CrawlResult,
        *,
        complete: bool,
    ) -> None:
        checkpoint_path = self._checkpoint_file_for_seed(seed_url)
        if checkpoint_path is None:
            return

        payload = {
            "seed_url": seed_url,
            "complete": complete,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "queue": list(queue),
            "seen": sorted(seen),
            "content_hashes": sorted(content_hashes),
            "result": result.to_dict(),
        }
        checkpoint_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_checkpoint(self, seed_url: str) -> dict[str, Any] | None:
        checkpoint_path = self._checkpoint_file_for_seed(seed_url)
        if checkpoint_path is None or not checkpoint_path.exists():
            return None

        try:
            payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        if payload.get("seed_url") != seed_url:
            return None
        if payload.get("complete"):
            return None
        return payload

    def _log_struct(self, event: str, **fields: Any) -> None:
        record = {"event": event, **fields}
        logger.info(json.dumps(record, sort_keys=True))

    def _emit_live_event(self, event: str, **fields: Any) -> None:
        if self._live_stream_file is None:
            return
        self._stream_sequence += 1
        payload = {
            "sequence": self._stream_sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        with self._live_stream_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


AsyncEmailCrawler = AsyncOsintCrawler
