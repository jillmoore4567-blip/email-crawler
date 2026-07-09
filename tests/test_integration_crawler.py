from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pytest
from aiohttp import web

from email_crawler.crawler import AsyncOsintCrawler, CrawlConfig
from email_crawler.cli import run as cli_run


async def _start_app(app: web.Application, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    return runner


@pytest.mark.asyncio
async def test_robots_compliance_and_extractors(unused_tcp_port: int) -> None:
    async def robots_handler(request: web.Request) -> web.Response:
        return web.Response(
            text="User-agent: *\nDisallow: /private\nSitemap: /sitemap.xml\n",
            content_type="text/plain",
        )

    async def sitemap_handler(request: web.Request) -> web.Response:
        body = """
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>/public</loc></url>
            <url><loc>/contact</loc></url>
        </urlset>
        """
        return web.Response(text=body, content_type="application/xml")

    async def security_handler(request: web.Request) -> web.Response:
        return web.Response(text="Contact: mailto:security@example.com\n", content_type="text/plain")

    async def feed_handler(request: web.Request) -> web.Response:
        return web.Response(text="<rss><channel><title>Feed</title></channel></rss>", content_type="application/rss+xml")

    async def root_handler(request: web.Request) -> web.Response:
        html = """
        <html><head><title>Root</title><meta name="description" content="Root page"/></head>
        <body>
            contact us: team@example.com
            phone: +1 555 111 2222
            <a href="/public">Public</a>
            <a href="/private">Private</a>
            <a href="/docs/file.pdf">PDF</a>
            <a href="https://twitter.com/example">Twitter</a>
            <a href="/contact">Contact</a>
                <img src="/assets/logo.png" />
                <link rel="alternate" type="application/rss+xml" href="/rss.xml" />
        </body></html>
        """
        return web.Response(text=html, content_type="text/html")

    async def public_handler(request: web.Request) -> web.Response:
        return web.Response(text="<html><head><title>Public</title></head><body>ok</body></html>", content_type="text/html")

    async def private_handler(request: web.Request) -> web.Response:
        return web.Response(text="<html><head><title>Private</title></head><body>secret</body></html>", content_type="text/html")

    async def contact_handler(request: web.Request) -> web.Response:
        return web.Response(text="<html><head><title>Contact</title></head><body>hello</body></html>", content_type="text/html")

    app = web.Application()
    app.router.add_get("/robots.txt", robots_handler)
    app.router.add_get("/sitemap.xml", sitemap_handler)
    app.router.add_get("/.well-known/security.txt", security_handler)
    app.router.add_get("/rss.xml", feed_handler)
    app.router.add_get("/", root_handler)
    app.router.add_get("/public", public_handler)
    app.router.add_get("/private", private_handler)
    app.router.add_get("/contact", contact_handler)

    port = unused_tcp_port
    runner = await _start_app(app, port)
    try:
        seed = f"http://127.0.0.1:{port}/"
        crawler = AsyncOsintCrawler(
            CrawlConfig(
                max_pages_per_seed=10,
                max_depth=2,
                allowed_domains=("127.0.0.1",),
                obey_robots_txt=True,
            )
        )
        result = (await crawler.crawl_many([seed]))[0]

        assert any("/private" in link for link in result.discovered_links)
        assert all("/private" not in url for url in result.visited_urls)
        assert result.blocked_by_robots >= 1
        assert "team@example.com" in result.emails
        assert any("555" in phone for phone in result.phones)
        assert any(link.endswith(".pdf") for link in result.documents)
        assert any(image.endswith("/assets/logo.png") for image in result.images)
        assert any("twitter.com" in acct for acct in result.social_accounts)

        finding_types = {item.finding_type for item in result.intelligence_findings}
        assert "robots" in finding_types
        assert "sitemap" in finding_types
        assert "security_txt" in finding_types
        assert "feed" in finding_types
        assert "contact_page" in finding_types
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_checkpoint_resume_and_retry_policy(tmp_path: Path, unused_tcp_port: int) -> None:
    calls = {"flaky": 0, "notfound": 0}

    async def robots_handler(request: web.Request) -> web.Response:
        return web.Response(text="User-agent: *\nAllow: /\n", content_type="text/plain")

    async def root_handler(request: web.Request) -> web.Response:
        return web.Response(
            text="""
            <html><body>
                <a href="/a">A</a>
                <a href="/flaky">Flaky</a>
                <a href="/notfound">Missing</a>
            </body></html>
            """,
            content_type="text/html",
        )

    async def a_handler(request: web.Request) -> web.Response:
        return web.Response(text="<html><body><a href='/b'>B</a></body></html>", content_type="text/html")

    async def b_handler(request: web.Request) -> web.Response:
        return web.Response(text="<html><body>end</body></html>", content_type="text/html")

    async def flaky_handler(request: web.Request) -> web.Response:
        calls["flaky"] += 1
        if calls["flaky"] == 1:
            return web.Response(status=500, text="temporary")
        return web.Response(text="<html><body>admin@example.com</body></html>", content_type="text/html")

    async def notfound_handler(request: web.Request) -> web.Response:
        calls["notfound"] += 1
        return web.Response(status=404, text="missing")

    app = web.Application()
    app.router.add_get("/robots.txt", robots_handler)
    app.router.add_get("/", root_handler)
    app.router.add_get("/a", a_handler)
    app.router.add_get("/b", b_handler)
    app.router.add_get("/flaky", flaky_handler)
    app.router.add_get("/notfound", notfound_handler)

    port = unused_tcp_port
    runner = await _start_app(app, port)
    try:
        seed = f"http://127.0.0.1:{port}/"
        checkpoint_dir = tmp_path / "checkpoints"

        first = AsyncOsintCrawler(
            CrawlConfig(
                max_pages_per_seed=1,
                max_depth=2,
                allowed_domains=("127.0.0.1",),
                checkpoint_dir=str(checkpoint_dir),
                checkpoint_every_pages=1,
                retry_statuses=(500,),
            )
        )
        first_result = (await first.crawl_many([seed]))[0]
        assert first_result.pages_crawled == 1

        second = AsyncOsintCrawler(
            CrawlConfig(
                max_pages_per_seed=4,
                max_depth=2,
                allowed_domains=("127.0.0.1",),
                checkpoint_dir=str(checkpoint_dir),
                checkpoint_every_pages=1,
                resume=True,
                retry_statuses=(500,),
            )
        )
        resumed_result = (await second.crawl_many([seed]))[0]

        assert resumed_result.pages_crawled >= 3
        assert resumed_result.retries >= 1
        assert "admin@example.com" in resumed_result.emails
        assert calls["flaky"] == 2
        assert calls["notfound"] == 1
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_synthetic_test_site_crawl_has_expected_coverage(unused_tcp_port: int) -> None:
    site_root = Path(__file__).resolve().parents[1] / "test_site"
    assert site_root.exists()

    app = web.Application()
    app.router.add_static("/", str(site_root), show_index=True)

    port = unused_tcp_port
    runner = await _start_app(app, port)
    try:
        seed = f"http://127.0.0.1:{port}/index.html"
        crawler = AsyncOsintCrawler(
            CrawlConfig(
                max_pages_per_seed=30,
                max_depth=3,
                allowed_domains=("127.0.0.1",),
                obey_robots_txt=True,
                collect_whois=False,
                collect_tls=False,
                collect_subdomains=False,
            )
        )
        result = (await crawler.crawl_many([seed]))[0]

        assert result.pages_crawled >= 18
        assert len(result.documents) >= 3
        assert len(result.images) >= 3
        assert all("/private/" not in url for url in result.visited_urls)

        finding_types = {item.finding_type for item in result.intelligence_findings}
        assert "robots" in finding_types
        assert "sitemap" in finding_types
        assert "security_txt" in finding_types
        assert "feed" in finding_types

        assert result.performance.requests_completed >= result.pages_crawled
        assert result.performance.fetch_time_seconds > 0
        assert result.performance.extraction_time_seconds > 0
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_end_to_end_cli_outputs_with_synthetic_site(tmp_path: Path, unused_tcp_port: int) -> None:
    site_root = Path(__file__).resolve().parents[1] / "test_site"
    assert site_root.exists()

    app = web.Application()
    app.router.add_static("/", str(site_root), show_index=True)

    port = unused_tcp_port
    runner = await _start_app(app, port)
    try:
        seed_file = tmp_path / "seeds.txt"
        seed_file.write_text(f"http://127.0.0.1:{port}/index.html\n", encoding="utf-8")

        out_stats = tmp_path / "stats.json"
        out_html = tmp_path / "report.html"
        out_sqlite = tmp_path / "findings.db"
        out_json = tmp_path / "results.json"
        out_csv = tmp_path / "results.csv"
        out_emails = tmp_path / "emails.txt"
        out_snapshot = tmp_path / "snapshot_diff.json"

        args = argparse.Namespace(
            seeds=str(seed_file),
            max_pages=40,
            max_depth=4,
            concurrency=8,
            thread_pool_workers=0,
            timeout=10.0,
            delay=0.0,
            retries=1,
            retry_statuses="429,500,502,503,504",
            retry_backoff_base=0.1,
            retry_backoff_max=1.0,
            user_agent="EmailCrawlerTestBot/1.0",
            rate_limit=0.0,
            ignore_robots=False,
            no_collect_robots=False,
            no_collect_sitemap=False,
            no_collect_security=False,
            no_collect_feeds=False,
            no_collect_contact_pages=False,
            no_collect_whois=True,
            no_collect_tls=True,
            no_collect_security_headers=False,
            no_collect_tech_fingerprint=False,
            no_collect_javascript_assets=False,
            no_collect_subdomains=True,
            collect_screenshots=False,
            screenshot_dir=str(tmp_path / "screens"),
            no_collect_broken_links=False,
            broken_links_max_checks_per_page=20,
            broken_links_include_external=False,
            max_links_per_page_saved=300,
            max_discovered_links_per_seed=5000,
            checkpoint_dir=str(tmp_path / "checkpoints"),
            resume=False,
            incremental=False,
            checkpoint_every_pages=10,
            cross_domain=False,
            allow_domain=["127.0.0.1"],
            out_emails=str(out_emails),
            out_json=str(out_json),
            out_csv=str(out_csv),
            out_stats=str(out_stats),
            out_snapshot_diff=str(out_snapshot),
            out_sqlite=str(out_sqlite),
            out_html=str(out_html),
            log_level="INFO",
            log_file="",
            config="config.yaml",
        )

        code = await cli_run(args)
        assert code == 0

        assert out_stats.exists()
        assert out_html.exists()
        assert out_sqlite.exists()
        assert out_snapshot.exists()

        stats = json.loads(out_stats.read_text(encoding="utf-8"))
        assert stats["pages_crawled"] >= 18
        assert stats["performance"]["aggregate"]["requests_completed"] >= 1
        assert stats["performance"]["aggregate"]["fetch_time_seconds"] > 0

        report_html = out_html.read_text(encoding="utf-8")
        assert "Performance Observability" in report_html
        assert "Snapshot Comparison" in report_html
        assert "Global Search" in report_html
        assert "Type Filters" in report_html
        assert "Pages Table" in report_html
        assert "Emails Table" in report_html
        assert "Documents Table" in report_html
        assert "Findings Table" in report_html
        assert "Page Details" in report_html
        assert "sortTable('pages'" in report_html
        assert "FILTER_STATE_KEY" in report_html
        assert "Crawl Metrics" in report_html
        assert "Email Domain Distribution" in report_html
        assert "Document Type Distribution" in report_html
        assert "Crawl Timing" in report_html
        assert "chartExportFormat" in report_html
        assert "Dark Mode" in report_html
        assert "toggleTheme()" in report_html
        assert "format === 'svg'" in report_html
        assert "Page Relationship Graph" in report_html
        assert "pageGraphPlot" in report_html
        assert "graphSeedFilter" in report_html
        assert "graphDomainFilter" in report_html
        assert "graphSnapshotFilter" in report_html
        assert "applyGraphFilters()" in report_html
        assert "renderPageGraph()" in report_html
        assert "plotly_click" in report_html
        assert "click a node to open Page Details" in report_html

        conn = sqlite3.connect(out_sqlite)
        try:
            run_count = conn.execute("SELECT COUNT(*) FROM crawl_runs").fetchone()[0]
            snapshot_count = conn.execute("SELECT COUNT(*) FROM page_snapshots").fetchone()[0]
        finally:
            conn.close()

        assert run_count >= 1
        assert snapshot_count >= 1
    finally:
        await runner.cleanup()
