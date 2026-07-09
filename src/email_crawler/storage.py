from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .crawler import CrawlResult


def persist_results_sqlite(
    results: list[CrawlResult],
    db_path: str,
    *,
    config_payload: dict[str, Any] | None = None,
    crawler_version: str = "0.1.0",
) -> str:
    run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    started_at = min((result.started_at for result in results), default=datetime.now(timezone.utc))
    completed_at = max(
        ((result.finished_at or result.started_at) for result in results),
        default=datetime.now(timezone.utc),
    )
    seeds_joined = ",".join(sorted({result.seed_url for result in results}))
    config_hash = hashlib.sha256(
        json.dumps(config_payload or {}, sort_keys=True).encode("utf-8")
    ).hexdigest()

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _apply_migrations(conn)

        conn.execute(
            """
            INSERT OR REPLACE INTO crawl_runs (
                run_id, started_at, completed_at, seed_url, config_hash, crawler_version, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                started_at.isoformat(),
                completed_at.isoformat(),
                seeds_joined,
                config_hash,
                crawler_version,
                "completed",
            ),
        )

        previous_run_id = _get_previous_run_id(conn, run_id)

        current_finding_ids: dict[str, set[str]] = {}

        for result in results:
            for intel in result.intelligence_findings:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO intelligence_findings (
                        run_id, seed_url, finding_type, url, status, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        result.seed_url,
                        intel.finding_type,
                        intel.url,
                        intel.status,
                        json.dumps(intel.details, sort_keys=True),
                    ),
                )
                _add_finding(current_finding_ids, "intelligence", f"{intel.url}|{intel.finding_type}")

            for finding in result.page_findings:
                _add_finding(current_finding_ids, "page", finding.url)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO pages (
                        run_id, seed_url, url, title, description, keywords, crawled_at, content_hash, http_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        result.seed_url,
                        finding.url,
                        finding.title,
                        finding.description,
                        ";".join(finding.keywords),
                        datetime.now(timezone.utc).isoformat(),
                        finding.content_hash,
                        finding.http_status,
                    ),
                )

                page_row = conn.execute(
                    "SELECT id FROM pages WHERE run_id = ? AND url = ?",
                    (run_id, finding.url),
                ).fetchone()
                if page_row:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO page_snapshots (
                            run_id, page_id, content_hash, http_status, title, last_seen
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            int(page_row[0]),
                            finding.content_hash,
                            finding.http_status,
                            finding.title,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )

                for link in finding.links:
                    conn.execute(
                        "INSERT OR IGNORE INTO links (run_id, source_url, target_url) VALUES (?, ?, ?)",
                        (run_id, finding.url, link),
                    )
                    _add_finding(current_finding_ids, "link", f"{finding.url}|{link}")

                for email in finding.emails:
                    conn.execute(
                        "INSERT OR IGNORE INTO emails (run_id, page_url, email) VALUES (?, ?, ?)",
                        (run_id, finding.url, email),
                    )
                    _add_finding(current_finding_ids, "email", f"{finding.url}|{email}")

                for phone in finding.phones:
                    conn.execute(
                        "INSERT OR IGNORE INTO phones (run_id, page_url, phone) VALUES (?, ?, ?)",
                        (run_id, finding.url, phone),
                    )
                    _add_finding(current_finding_ids, "phone", f"{finding.url}|{phone}")

                for doc in finding.documents:
                    conn.execute(
                        "INSERT OR IGNORE INTO documents (run_id, page_url, document_url) VALUES (?, ?, ?)",
                        (run_id, finding.url, doc),
                    )
                    _add_finding(current_finding_ids, "document", f"{finding.url}|{doc}")

                for profile in finding.social_accounts:
                    conn.execute(
                        "INSERT OR IGNORE INTO social_profiles (run_id, page_url, profile_url) VALUES (?, ?, ?)",
                        (run_id, finding.url, profile),
                    )
                    _add_finding(current_finding_ids, "social_profile", f"{finding.url}|{profile}")

                for image_url in finding.images:
                    conn.execute(
                        "INSERT OR IGNORE INTO images (run_id, page_url, image_url) VALUES (?, ?, ?)",
                        (run_id, finding.url, image_url),
                    )
                    _add_finding(current_finding_ids, "image", f"{finding.url}|{image_url}")

                for js_url in finding.javascript_assets:
                    conn.execute(
                        "INSERT OR IGNORE INTO javascript_assets (run_id, page_url, asset_url) VALUES (?, ?, ?)",
                        (run_id, finding.url, js_url),
                    )
                    _add_finding(current_finding_ids, "javascript_asset", f"{finding.url}|{js_url}")

                for tech in finding.technologies:
                    conn.execute(
                        "INSERT OR IGNORE INTO technologies (run_id, page_url, technology) VALUES (?, ?, ?)",
                        (run_id, finding.url, tech),
                    )
                    _add_finding(current_finding_ids, "technology", f"{finding.url}|{tech}")

                for header_name, header_value in finding.security_headers.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO security_headers (run_id, page_url, header_name, header_value) VALUES (?, ?, ?, ?)",
                        (run_id, finding.url, header_name, header_value),
                    )
                    _add_finding(
                        current_finding_ids,
                        "security_header",
                        f"{finding.url}|{header_name}:{header_value}",
                    )

                for broken_url in finding.broken_links:
                    conn.execute(
                        "INSERT OR IGNORE INTO broken_links (run_id, page_url, broken_url) VALUES (?, ?, ?)",
                        (run_id, finding.url, broken_url),
                    )
                    _add_finding(current_finding_ids, "broken_link", f"{finding.url}|{broken_url}")

            if result.unchanged_urls and previous_run_id:
                _carry_forward_unchanged_pages(
                    conn,
                    previous_run_id,
                    run_id,
                    result.seed_url,
                    sorted(result.unchanged_urls),
                    current_finding_ids,
                )
        previous_finding_ids = _load_finding_snapshot_ids(conn, previous_run_id)

        for finding_type, ids in current_finding_ids.items():
            for finding_id in ids:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO finding_snapshots (
                        run_id, finding_type, finding_id, status
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (run_id, finding_type, finding_id, "present"),
                )

        for finding_type, previous_ids in previous_finding_ids.items():
            removed_ids = previous_ids - current_finding_ids.get(finding_type, set())
            for finding_id in removed_ids:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO finding_snapshots (
                        run_id, finding_type, finding_id, status
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (run_id, finding_type, finding_id, "removed"),
                )

        conn.commit()
    finally:
        conn.close()

    return run_id


def compare_run_with_previous(db_path: str, run_id: str) -> dict[str, Any]:
    conn = sqlite3.connect(Path(db_path))
    try:
        _apply_migrations(conn)
        previous_run_id = _get_previous_run_id(conn, run_id)
        if not previous_run_id:
            return {
                "run_id": run_id,
                "previous_run_id": None,
                "new_pages": 0,
                "removed_pages": 0,
                "changed_pages": 0,
                "new_findings": 0,
                "removed_findings": 0,
                "duration_seconds": 0.0,
                "page_changes": [],
            }

        current_pages = _load_pages_by_url(conn, run_id)
        previous_pages = _load_pages_by_url(conn, previous_run_id)

        current_urls = set(current_pages)
        previous_urls = set(previous_pages)

        new_urls = sorted(current_urls - previous_urls)
        removed_urls = sorted(previous_urls - current_urls)
        shared_urls = sorted(current_urls & previous_urls)

        page_changes: list[dict[str, Any]] = []
        for url in new_urls:
            cur = current_pages[url]
            page_changes.append(
                {
                    "url": url,
                    "change_type": "new",
                    "previous_content_hash": "",
                    "current_content_hash": cur["content_hash"],
                    "previous_timestamp": "",
                    "current_timestamp": cur["crawled_at"],
                    "finding_refs": _finding_refs_for_url(conn, run_id, url),
                }
            )

        changed_count = 0
        for url in shared_urls:
            cur = current_pages[url]
            prev = previous_pages[url]
            if cur["content_hash"] == prev["content_hash"]:
                continue
            changed_count += 1
            page_changes.append(
                {
                    "url": url,
                    "change_type": "changed",
                    "previous_content_hash": prev["content_hash"],
                    "current_content_hash": cur["content_hash"],
                    "previous_timestamp": prev["crawled_at"],
                    "current_timestamp": cur["crawled_at"],
                    "finding_refs": _finding_refs_for_url(conn, run_id, url),
                }
            )

        for url in removed_urls:
            prev = previous_pages[url]
            page_changes.append(
                {
                    "url": url,
                    "change_type": "removed",
                    "previous_content_hash": prev["content_hash"],
                    "current_content_hash": "",
                    "previous_timestamp": prev["crawled_at"],
                    "current_timestamp": "",
                    "finding_refs": _finding_refs_for_url(conn, previous_run_id, url),
                }
            )

        new_pages = len(new_urls)
        removed_pages = len(removed_urls)
        changed_pages = changed_count

        new_findings = conn.execute(
            """
            SELECT COUNT(*)
            FROM finding_snapshots cur
            WHERE cur.run_id = ?
              AND cur.status = 'present'
              AND NOT EXISTS (
                  SELECT 1 FROM finding_snapshots prev
                  WHERE prev.run_id = ?
                    AND prev.status = 'present'
                    AND prev.finding_type = cur.finding_type
                    AND prev.finding_id = cur.finding_id
              )
            """,
            (run_id, previous_run_id),
        ).fetchone()[0]

        removed_findings = conn.execute(
            """
            SELECT COUNT(*)
            FROM finding_snapshots cur
            WHERE cur.run_id = ?
              AND cur.status = 'removed'
            """,
            (run_id,),
        ).fetchone()[0]

        duration_seconds = conn.execute(
            """
            SELECT (julianday(completed_at) - julianday(started_at)) * 86400.0
            FROM crawl_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()[0]

        return {
            "run_id": run_id,
            "previous_run_id": previous_run_id,
            "new_pages": int(new_pages),
            "removed_pages": int(removed_pages),
            "changed_pages": int(changed_pages),
            "new_findings": int(new_findings),
            "removed_findings": int(removed_findings),
            "duration_seconds": round(float(duration_seconds or 0.0), 3),
            "page_changes": page_changes,
        }
    finally:
        conn.close()


def load_latest_page_hashes(db_path: str) -> dict[str, str]:
    path = Path(db_path)
    if not path.exists():
        return {}

    conn = sqlite3.connect(path)
    try:
        _apply_migrations(conn)
        latest_run_id = _latest_completed_run_id(conn)
        if not latest_run_id:
            return {}

        rows = conn.execute(
            "SELECT url, content_hash FROM pages WHERE run_id = ? AND content_hash IS NOT NULL",
            (latest_run_id,),
        ).fetchall()
        return {str(url): str(content_hash) for url, content_hash in rows if url and content_hash}
    finally:
        conn.close()


def load_latest_links_by_source(db_path: str) -> dict[str, list[str]]:
    path = Path(db_path)
    if not path.exists():
        return {}

    conn = sqlite3.connect(path)
    try:
        _apply_migrations(conn)
        latest_run_id = _latest_completed_run_id(conn)
        if not latest_run_id:
            return {}

        rows = conn.execute(
            "SELECT source_url, target_url FROM links WHERE run_id = ?",
            (latest_run_id,),
        ).fetchall()
        mapping: dict[str, list[str]] = {}
        for source, target in rows:
            if not source or not target:
                continue
            mapping.setdefault(str(source), []).append(str(target))
        return mapping
    finally:
        conn.close()


def _add_finding(store: dict[str, set[str]], finding_type: str, finding_id: str) -> None:
    store.setdefault(finding_type, set()).add(finding_id)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )

    current_version_row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current_version = int(current_version_row[0] or 0)

    # Legacy compatibility: existing databases may already have core tables but no
    # schema_version history. Set baseline to migration 1 in that case.
    if current_version == 0:
        has_legacy_pages = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pages'"
        ).fetchone()
        if has_legacy_pages:
            conn.execute(
                "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
                (1, datetime.now(timezone.utc).isoformat()),
            )
            current_version = 1

    migration_dir = Path(__file__).resolve().parent / "migrations"
    for sql_file in sorted(migration_dir.glob("*.sql")):
        raw_name = sql_file.name.split("_", 1)[0]
        if not raw_name.isdigit():
            continue
        target_version = int(raw_name)
        if target_version <= current_version:
            continue

        conn.executescript(sql_file.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (target_version, datetime.now(timezone.utc).isoformat()),
        )
        current_version = target_version

    _ensure_column(conn, "pages", "keywords", "TEXT")
    _ensure_column(conn, "pages", "content_hash", "TEXT")
    _ensure_column(conn, "pages", "http_status", "INTEGER")


def _latest_completed_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
        SELECT run_id
        FROM crawl_runs
        WHERE status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
        """
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _get_previous_run_id(conn: sqlite3.Connection, current_run_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT run_id
        FROM crawl_runs
        WHERE status = 'completed' AND run_id != ?
        ORDER BY completed_at DESC
        LIMIT 1
        """,
        (current_run_id,),
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _load_finding_snapshot_ids(conn: sqlite3.Connection, run_id: str | None) -> dict[str, set[str]]:
    if not run_id:
        return {}

    rows = conn.execute(
        """
        SELECT finding_type, finding_id
        FROM finding_snapshots
        WHERE run_id = ? AND status = 'present'
        """,
        (run_id,),
    ).fetchall()
    out: dict[str, set[str]] = {}
    for finding_type, finding_id in rows:
        out.setdefault(str(finding_type), set()).add(str(finding_id))
    return out


def _carry_forward_unchanged_pages(
    conn: sqlite3.Connection,
    previous_run_id: str,
    current_run_id: str,
    seed_url: str,
    urls: list[str],
    current_finding_ids: dict[str, set[str]],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for url in urls:
        prev_page = conn.execute(
            """
            SELECT title, description, keywords, content_hash, http_status
            FROM pages
            WHERE run_id = ? AND url = ?
            """,
            (previous_run_id, url),
        ).fetchone()
        if not prev_page:
            continue

        conn.execute(
            """
            INSERT OR REPLACE INTO pages (
                run_id, seed_url, url, title, description, keywords, crawled_at, content_hash, http_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current_run_id,
                seed_url,
                url,
                prev_page[0],
                prev_page[1],
                prev_page[2],
                now,
                prev_page[3],
                prev_page[4],
            ),
        )

        page_row = conn.execute(
            "SELECT id FROM pages WHERE run_id = ? AND url = ?",
            (current_run_id, url),
        ).fetchone()
        if page_row:
            conn.execute(
                """
                INSERT OR REPLACE INTO page_snapshots (
                    run_id, page_id, content_hash, http_status, title, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    current_run_id,
                    int(page_row[0]),
                    prev_page[3],
                    prev_page[4],
                    prev_page[0],
                    now,
                ),
            )

        _add_finding(current_finding_ids, "page", url)

        prev_findings = conn.execute(
            """
            SELECT finding_type, finding_id
            FROM finding_snapshots
            WHERE run_id = ? AND status = 'present'
              AND (finding_id = ? OR finding_id LIKE ?)
            """,
            (previous_run_id, url, f"{url}|%"),
        ).fetchall()

        for finding_type, finding_id in prev_findings:
            _add_finding(current_finding_ids, str(finding_type), str(finding_id))

        prev_links = conn.execute(
            """
            SELECT target_url
            FROM links
            WHERE run_id = ? AND source_url = ?
            """,
            (previous_run_id, url),
        ).fetchall()
        for (target_url,) in prev_links:
            if not target_url:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO links (run_id, source_url, target_url) VALUES (?, ?, ?)",
                (current_run_id, url, str(target_url)),
            )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row[1] for row in info}
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _load_pages_by_url(conn: sqlite3.Connection, run_id: str) -> dict[str, dict[str, str]]:
    rows = conn.execute(
        "SELECT url, IFNULL(content_hash, ''), IFNULL(crawled_at, '') FROM pages WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    return {
        str(url): {"content_hash": str(content_hash), "crawled_at": str(crawled_at)}
        for url, content_hash, crawled_at in rows
        if url
    }


def _finding_refs_for_url(conn: sqlite3.Connection, run_id: str, url: str) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT finding_type, COUNT(*)
        FROM finding_snapshots
        WHERE run_id = ?
          AND status = 'present'
          AND (finding_id = ? OR finding_id LIKE ?)
        GROUP BY finding_type
        ORDER BY finding_type
        """,
        (run_id, url, f"{url}|%"),
    ).fetchall()
    return {
        "assets_anchor": "#assets-table",
        "intel_anchor": "#intel-table",
        "counts_by_type": {str(finding_type): int(count) for finding_type, count in rows},
    }
