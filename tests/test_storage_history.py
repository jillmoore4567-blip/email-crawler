from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from email_crawler.crawler import CrawlResult, PageFinding
from email_crawler.storage import compare_run_with_previous, persist_results_sqlite


LATEST_SCHEMA_VERSION = 3


def _make_result(*, seed: str, page_url: str, title: str, emails: list[str], links: list[str]) -> CrawlResult:
    result = CrawlResult(seed_url=seed)
    now = datetime.now(timezone.utc)
    result.started_at = now
    result.finished_at = now
    result.page_findings = [
        PageFinding(
            url=page_url,
            title=title,
            description="desc",
            keywords=["k1"],
            emails=emails,
            links=links,
            content_hash=f"hash-{title}",
            http_status=200,
        )
    ]
    result.pages_crawled = 1
    result.visited_urls = {page_url}
    result.discovered_links = set(links)
    return result


def test_migrations_and_snapshot_diff(tmp_path: Path) -> None:
    db_path = tmp_path / "findings.db"

    first = _make_result(
        seed="https://example.test",
        page_url="https://example.test/index.html",
        title="Home",
        emails=["info@example.test"],
        links=["https://example.test/about.html"],
    )
    run1 = persist_results_sqlite([first], str(db_path), config_payload={"a": 1})
    diff1 = compare_run_with_previous(str(db_path), run1)

    assert diff1["previous_run_id"] is None

    second = _make_result(
        seed="https://example.test",
        page_url="https://example.test/index.html",
        title="Home V2",
        emails=["security@example.test"],
        links=["https://example.test/about.html", "https://example.test/contact.html"],
    )
    run2 = persist_results_sqlite([second], str(db_path), config_payload={"a": 2})
    diff2 = compare_run_with_previous(str(db_path), run2)

    assert diff2["previous_run_id"] == run1
    assert diff2["changed_pages"] >= 1
    assert diff2["new_findings"] >= 1
    assert diff2["removed_findings"] >= 1
    assert isinstance(diff2["page_changes"], list)
    assert any(item.get("change_type") == "changed" for item in diff2["page_changes"])
    changed_items = [item for item in diff2["page_changes"] if item.get("change_type") == "changed"]
    assert changed_items
    assert "previous_content_hash" in changed_items[0]
    assert "current_content_hash" in changed_items[0]


def test_schema_version_table_populated(tmp_path: Path) -> None:
    db_path = tmp_path / "findings.db"
    result = _make_result(
        seed="https://example.test",
        page_url="https://example.test/index.html",
        title="Home",
        emails=["info@example.test"],
        links=[],
    )
    persist_results_sqlite([result], str(db_path), config_payload={})

    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        versions = [row[0] for row in conn.execute("SELECT version FROM schema_version ORDER BY version")]
    finally:
        conn.close()

    assert versions == [1, 2, 3]


def test_incremental_unchanged_pages_not_marked_removed(tmp_path: Path) -> None:
    db_path = tmp_path / "findings.db"

    first = _make_result(
        seed="https://example.test",
        page_url="https://example.test/index.html",
        title="Home",
        emails=["info@example.test"],
        links=["https://example.test/about.html"],
    )
    run1 = persist_results_sqlite([first], str(db_path), config_payload={"incremental": False})

    second = CrawlResult(seed_url="https://example.test")
    now = datetime.now(timezone.utc)
    second.started_at = now
    second.finished_at = now
    second.unchanged_pages_skipped = 1
    second.unchanged_urls = {"https://example.test/index.html"}
    run2 = persist_results_sqlite([second], str(db_path), config_payload={"incremental": True})

    diff = compare_run_with_previous(str(db_path), run2)
    assert diff["previous_run_id"] == run1
    assert diff["removed_pages"] == 0
    assert diff["removed_findings"] == 0


def test_legacy_database_is_upgraded_by_migration_runner(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    legacy_url = "https://example.test/legacy.html"
    legacy_seen_at = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                seed_url TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                description TEXT,
                crawled_at TEXT NOT NULL
            );
            CREATE TABLE links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                source_url TEXT NOT NULL,
                target_url TEXT NOT NULL,
                UNIQUE(run_id, source_url, target_url)
            );
            CREATE TABLE emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                email TEXT NOT NULL,
                UNIQUE(run_id, page_url, email)
            );
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                document_url TEXT NOT NULL,
                UNIQUE(run_id, page_url, document_url)
            );
            CREATE TABLE phones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                phone TEXT NOT NULL,
                UNIQUE(run_id, page_url, phone)
            );
            CREATE TABLE social_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                profile_url TEXT NOT NULL,
                UNIQUE(run_id, page_url, profile_url)
            );
            CREATE TABLE images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                image_url TEXT NOT NULL,
                UNIQUE(run_id, page_url, image_url)
            );
            CREATE TABLE javascript_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                asset_url TEXT NOT NULL,
                UNIQUE(run_id, page_url, asset_url)
            );
            CREATE TABLE technologies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                technology TEXT NOT NULL,
                UNIQUE(run_id, page_url, technology)
            );
            CREATE TABLE security_headers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                header_name TEXT NOT NULL,
                header_value TEXT NOT NULL,
                UNIQUE(run_id, page_url, header_name)
            );
            CREATE TABLE broken_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                broken_url TEXT NOT NULL,
                UNIQUE(run_id, page_url, broken_url)
            );
            CREATE TABLE intelligence_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                seed_url TEXT NOT NULL,
                finding_type TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                details_json TEXT NOT NULL,
                UNIQUE(run_id, finding_type, url)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO pages(run_id, seed_url, url, title, description, crawled_at)
            VALUES('legacy-run', 'https://example.test', ?, 'Legacy', '', ?)
            """,
            (legacy_url, legacy_seen_at),
        )
        conn.execute(
            "INSERT INTO emails(run_id, page_url, email) VALUES('legacy-run', ?, 'legacy@example.test')",
            (legacy_url,),
        )
        conn.commit()
    finally:
        conn.close()

    result = _make_result(
        seed="https://example.test",
        page_url="https://example.test/index.html",
        title="Home",
        emails=["info@example.test"],
        links=[],
    )
    run1 = persist_results_sqlite([result], str(db_path), config_payload={"from_legacy": True})
    run2 = persist_results_sqlite([result], str(db_path), config_payload={"from_legacy": True, "second": True})

    diff = compare_run_with_previous(str(db_path), run2)

    verify = sqlite3.connect(db_path)
    try:
        versions = [row[0] for row in verify.execute("SELECT version FROM schema_version ORDER BY version")]
        schema_row_count = verify.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
        run_count = verify.execute("SELECT COUNT(*) FROM crawl_runs").fetchone()[0]
        tables = {
            row[0]
            for row in verify.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        preserved_page = verify.execute(
            "SELECT run_id, seed_url, url, title, crawled_at FROM pages WHERE run_id = 'legacy-run' AND url = ?",
            (legacy_url,),
        ).fetchone()
        preserved_email = verify.execute(
            "SELECT email FROM emails WHERE run_id = 'legacy-run' AND page_url = ?",
            (legacy_url,),
        ).fetchone()
    finally:
        verify.close()

    assert versions == [1, 2, 3]
    assert schema_row_count == LATEST_SCHEMA_VERSION
    assert run_count >= 2
    assert preserved_page == ("legacy-run", "https://example.test", legacy_url, "Legacy", legacy_seen_at)
    assert preserved_email == ("legacy@example.test",)
    assert {"crawl_runs", "page_snapshots", "finding_snapshots"}.issubset(tables)
    assert diff["previous_run_id"] == run1
    assert diff["run_id"] == run2
    assert diff["new_pages"] == 0
    assert diff["changed_pages"] == 0
