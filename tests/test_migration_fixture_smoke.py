from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from email_crawler.crawler import CrawlResult, PageFinding
from email_crawler.storage import compare_run_with_previous, persist_results_sqlite

LATEST_SCHEMA_VERSION = 5
FIXTURE_DB = Path(__file__).resolve().parent / "fixtures" / "legacy_v1.db"


def _make_result() -> CrawlResult:
    result = CrawlResult(seed_url="https://fixture.test")
    result.page_findings = [
        PageFinding(
            url="https://fixture.test/index.html",
            title="Current Home",
            description="current row",
            emails=["current@fixture.test"],
            content_hash="hash-current-home",
            http_status=200,
        )
    ]
    result.pages_crawled = 1
    result.visited_urls = {"https://fixture.test/index.html"}
    return result


def test_legacy_fixture_migrates_and_is_idempotent(tmp_path: Path) -> None:
    assert FIXTURE_DB.exists()
    db_path = tmp_path / "legacy_copy.db"
    shutil.copy2(FIXTURE_DB, db_path)

    run1 = persist_results_sqlite([_make_result()], str(db_path), config_payload={"fixture": 1})
    run2 = persist_results_sqlite([_make_result()], str(db_path), config_payload={"fixture": 2})
    diff = compare_run_with_previous(str(db_path), run2)

    conn = sqlite3.connect(db_path)
    try:
        versions = [row[0] for row in conn.execute("SELECT version FROM schema_version ORDER BY version")]
        preserved_legacy_page = conn.execute(
            "SELECT title FROM pages WHERE run_id = 'legacy-run' AND url = 'https://fixture.test/index.html'"
        ).fetchone()
        preserved_legacy_email = conn.execute(
            "SELECT email FROM emails WHERE run_id = 'legacy-run' AND page_url = 'https://fixture.test/index.html'"
        ).fetchone()
        has_runs = conn.execute("SELECT COUNT(*) FROM crawl_runs").fetchone()[0]
        has_page_snapshots = conn.execute("SELECT COUNT(*) FROM page_snapshots").fetchone()[0]
        has_finding_snapshots = conn.execute("SELECT COUNT(*) FROM finding_snapshots").fetchone()[0]
    finally:
        conn.close()

    assert versions == [1, 2, 3, 4, 5]
    assert versions[-1] == LATEST_SCHEMA_VERSION
    assert preserved_legacy_page == ("Legacy Home",)
    assert preserved_legacy_email == ("legacy@fixture.test",)
    assert has_runs >= 2
    assert has_page_snapshots >= 1
    assert has_finding_snapshots >= 1
    assert diff["run_id"] == run2
    assert diff["previous_run_id"] == run1
    assert diff["new_pages"] == 0
    assert diff["changed_pages"] == 0
