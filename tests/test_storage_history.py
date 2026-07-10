from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from email_crawler.crawler import CrawlResult, PageFinding
from email_crawler.intelligence import IntelligenceFinding
from email_crawler.storage import (
    compare_run_with_previous,
    load_finding_snapshot_timeline,
    load_latest_links_by_source,
    load_page_snapshot_timeline,
    persist_results_sqlite,
)


LATEST_SCHEMA_VERSION = 5


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

    assert versions == [1, 2, 3, 4, 5]


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


def test_incremental_unchanged_pages_preserve_links_for_future_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "findings.db"
    seed = "https://example.test"
    page_url = "https://example.test/index.html"
    linked_url = "https://example.test/about.html"

    first = _make_result(
        seed=seed,
        page_url=page_url,
        title="Home",
        emails=["info@example.test"],
        links=[linked_url],
    )
    persist_results_sqlite([first], str(db_path), config_payload={"incremental": False})

    second = CrawlResult(seed_url=seed)
    now = datetime.now(timezone.utc)
    second.started_at = now
    second.finished_at = now
    second.unchanged_pages_skipped = 1
    second.unchanged_urls = {page_url}
    persist_results_sqlite([second], str(db_path), config_payload={"incremental": True})

    latest_links = load_latest_links_by_source(str(db_path))

    assert latest_links[page_url] == [linked_url]


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

    assert versions == [1, 2, 3, 4, 5]
    assert schema_row_count == LATEST_SCHEMA_VERSION
    assert run_count >= 2
    assert preserved_page == ("legacy-run", "https://example.test", legacy_url, "Legacy", legacy_seen_at)
    assert preserved_email == ("legacy@example.test",)
    assert {"crawl_runs", "page_snapshots", "finding_snapshots"}.issubset(tables)
    assert diff["previous_run_id"] == run1
    assert diff["run_id"] == run2
    assert diff["new_pages"] == 0
    assert diff["changed_pages"] == 0


def test_page_snapshot_timeline_is_deterministic(tmp_path: Path) -> None:
    db_path = tmp_path / "findings.db"
    seed = "https://example.test"
    page_url = "https://example.test/index.html"

    first = _make_result(
        seed=seed,
        page_url=page_url,
        title="Home",
        emails=["first@example.test"],
        links=[],
    )
    run1 = persist_results_sqlite([first], str(db_path), config_payload={"run": 1})

    second = _make_result(
        seed=seed,
        page_url=page_url,
        title="Home v2",
        emails=["second@example.test"],
        links=[],
    )
    run2 = persist_results_sqlite([second], str(db_path), config_payload={"run": 2})

    timeline = load_page_snapshot_timeline(str(db_path), seed_url=seed, page_url=page_url)

    assert [entry["run_id"] for entry in timeline] == [run1, run2]
    assert [entry["title"] for entry in timeline] == ["Home", "Home v2"]
    assert timeline[0]["first_seen"] == timeline[1]["first_seen"]
    assert timeline[0]["page_uid"] == timeline[1]["page_uid"]
    assert timeline[0]["completed_at"] <= timeline[1]["completed_at"]


def test_snapshot_timeline_helpers_cover_long_history(tmp_path: Path) -> None:
    db_path = tmp_path / "findings.db"
    seed = "https://example.test"
    page_url = "https://example.test/history"

    run_ids: list[str] = []
    for run_number in range(1, 13):
        result = _make_result(
            seed=seed,
            page_url=page_url,
            title=f"History {run_number}",
            emails=[f"run{run_number}@example.test"],
            links=[f"https://example.test/{run_number}"],
        )
        run_ids.append(persist_results_sqlite([result], str(db_path), config_payload={"run": run_number}))

    page_timeline = load_page_snapshot_timeline(str(db_path), seed_url=seed, page_url=page_url)
    email_timeline = load_finding_snapshot_timeline(
        str(db_path),
        finding_type="email",
        finding_id=f"{page_url}|run12@example.test",
    )

    assert len(page_timeline) == 12
    assert [entry["run_id"] for entry in page_timeline] == run_ids
    assert page_timeline[0]["title"] == "History 1"
    assert page_timeline[-1]["title"] == "History 12"
    assert page_timeline[-1]["content_hash"] == "hash-History 12"

    assert len(email_timeline) == 1
    assert email_timeline[0]["run_id"] == run_ids[-1]
    assert email_timeline[0]["status"] == "present"


def test_finding_snapshot_timeline_tracks_order_and_status_transitions(tmp_path: Path) -> None:
    db_path = tmp_path / "findings.db"
    seed = "https://example.test"
    page_url = "https://example.test/transition"
    tracked_email = "timeline@example.test"
    finding_id = f"{page_url}|{tracked_email}"

    run1 = persist_results_sqlite(
        [
            _make_result(
                seed=seed,
                page_url=page_url,
                title="Transition 1",
                emails=[tracked_email],
                links=[],
            )
        ],
        str(db_path),
        config_payload={"run": 1},
    )

    run2 = persist_results_sqlite(
        [
            _make_result(
                seed=seed,
                page_url=page_url,
                title="Transition 2",
                emails=[],
                links=[],
            )
        ],
        str(db_path),
        config_payload={"run": 2},
    )

    run3 = persist_results_sqlite(
        [
            _make_result(
                seed=seed,
                page_url=page_url,
                title="Transition 3",
                emails=[tracked_email],
                links=[],
            )
        ],
        str(db_path),
        config_payload={"run": 3},
    )

    timeline = load_finding_snapshot_timeline(
        str(db_path),
        finding_type="email",
        finding_id=finding_id,
    )

    assert [entry["run_id"] for entry in timeline] == [run1, run2, run3]
    assert [entry["status"] for entry in timeline] == ["present", "removed", "present"]
    assert timeline[0]["completed_at"] <= timeline[1]["completed_at"] <= timeline[2]["completed_at"]


def test_provenance_page_and_artifact_lifecycle(tmp_path: Path) -> None:
    db_path = tmp_path / "findings.db"
    seed = "https://example.test"
    page_url = "https://example.test/index.html"

    first = _make_result(
        seed=seed,
        page_url=page_url,
        title="Home",
        emails=["info@example.test"],
        links=["https://example.test/about.html"],
    )
    persist_results_sqlite([first], str(db_path), config_payload={"run": 1})

    second = _make_result(
        seed=seed,
        page_url=page_url,
        title="Home v2",
        emails=["info@example.test"],
        links=["https://example.test/about.html", "https://example.test/contact.html"],
    )
    run2 = persist_results_sqlite([second], str(db_path), config_payload={"run": 2})

    conn = sqlite3.connect(db_path)
    try:
        page_rows = conn.execute(
            """
            SELECT run_id, page_uid, first_seen, last_seen
            FROM pages
            WHERE url = ?
            ORDER BY last_seen ASC
            """,
            (page_url,),
        ).fetchall()
        assert len(page_rows) == 2
        assert page_rows[0][1] == page_rows[1][1]
        assert page_rows[0][2] == page_rows[1][2]
        assert page_rows[1][3] >= page_rows[1][2]

        run_uid_row = conn.execute(
            "SELECT run_uid FROM crawl_runs WHERE run_id = ?",
            (run2,),
        ).fetchone()
        assert run_uid_row == (run2,)

        artifact_rows = conn.execute(
            """
            SELECT artifact_type, artifact_value, first_seen, last_seen, last_run_id
            FROM artifact_provenance
            WHERE artifact_type = 'email' AND artifact_value = 'info@example.test'
            """
        ).fetchall()
        assert len(artifact_rows) == 1
        artifact = artifact_rows[0]
        assert artifact[2] <= artifact[3]
        assert artifact[4] == run2
    finally:
        conn.close()


def _make_result_with_intelligence(
    *,
    seed: str,
    page_url: str,
    title: str,
    intelligence: list[tuple[str, str]],
    unchanged_urls: set[str] | None = None,
) -> CrawlResult:
    result = CrawlResult(seed_url=seed)
    now = datetime.now(timezone.utc)
    result.started_at = now
    result.finished_at = now
    if unchanged_urls:
        result.unchanged_urls = set(unchanged_urls)
        result.unchanged_pages_skipped = len(unchanged_urls)
    else:
        result.page_findings = [
            PageFinding(
                url=page_url,
                title=title,
                description="desc",
                keywords=["k1"],
                content_hash=f"hash-{title}",
                http_status=200,
            )
        ]
        result.pages_crawled = 1
        result.visited_urls = {page_url}
    result.intelligence_findings = [
        IntelligenceFinding(
            finding_type=finding_type,
            url=url,
            status="ok",
            details={"source": "test"},
        )
        for finding_type, url in intelligence
    ]
    return result


def test_intelligence_provenance_lifecycle_across_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "findings.db"
    seed = "https://example.test"
    page_url = "https://example.test/contact"

    first = _make_result_with_intelligence(
        seed=seed,
        page_url=page_url,
        title="Home",
        intelligence=[("contact_page", page_url)],
    )
    run1 = persist_results_sqlite([first], str(db_path), config_payload={"run": 1})

    second = _make_result_with_intelligence(
        seed=seed,
        page_url=page_url,
        title="Ignored",
        intelligence=[],
        unchanged_urls={page_url},
    )
    run2 = persist_results_sqlite([second], str(db_path), config_payload={"run": 2})

    third = _make_result_with_intelligence(
        seed=seed,
        page_url=page_url,
        title="Home v2",
        intelligence=[("feed", page_url)],
    )
    run3 = persist_results_sqlite([third], str(db_path), config_payload={"run": 3})
    diff3 = compare_run_with_previous(str(db_path), run3)

    fourth = _make_result_with_intelligence(
        seed=seed,
        page_url=page_url,
        title="Home v3",
        intelligence=[],
    )
    run4 = persist_results_sqlite([fourth], str(db_path), config_payload={"run": 4})
    diff4 = compare_run_with_previous(str(db_path), run4)

    conn = sqlite3.connect(db_path)
    try:
        # Canonical intelligence key should be stable and include subtype in artifact_value.
        contact_row = conn.execute(
            """
            SELECT artifact_type, artifact_value, first_seen, last_seen, last_run_id
            FROM artifact_provenance
            WHERE artifact_type = 'intelligence' AND artifact_value = ?
            """,
            (f"{page_url}|contact_page",),
        ).fetchone()
        assert contact_row is not None
        assert contact_row[0] == "intelligence"
        assert contact_row[4] == run2
        assert str(contact_row[2]) <= str(contact_row[3])

        feed_row = conn.execute(
            """
            SELECT artifact_type, artifact_value, first_seen, last_seen, last_run_id
            FROM artifact_provenance
            WHERE artifact_type = 'intelligence' AND artifact_value = ?
            """,
            (f"{page_url}|feed",),
        ).fetchone()
        assert feed_row is not None
        assert feed_row[4] == run3

        # Ensure first_seen persists while last_seen advances for unchanged intelligence carried forward.
        snapshots = conn.execute(
            """
            SELECT run_id, status
            FROM finding_snapshots
            WHERE finding_type = 'intelligence' AND finding_id = ?
            ORDER BY rowid ASC
            """,
            (f"{page_url}|contact_page",),
        ).fetchall()
        assert (run1, "present") in snapshots
        assert (run2, "present") in snapshots
        assert (run3, "removed") in snapshots

        removed_feed = conn.execute(
            """
            SELECT status
            FROM finding_snapshots
            WHERE run_id = ? AND finding_type = 'intelligence' AND finding_id = ?
            """,
            (run4, f"{page_url}|feed"),
        ).fetchone()
        assert removed_feed == ("removed",)
    finally:
        conn.close()

    assert diff3["new_findings"] >= 1
    assert diff3["removed_findings"] >= 1
    assert diff4["removed_findings"] >= 1
