CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    seed_url TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    description TEXT,
    keywords TEXT,
    crawled_at TEXT NOT NULL,
    content_hash TEXT,
    http_status INTEGER,
    UNIQUE(run_id, url)
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    UNIQUE(run_id, source_url, target_url)
);

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    email TEXT NOT NULL,
    UNIQUE(run_id, page_url, email)
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    document_url TEXT NOT NULL,
    UNIQUE(run_id, page_url, document_url)
);

CREATE TABLE IF NOT EXISTS phones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    phone TEXT NOT NULL,
    UNIQUE(run_id, page_url, phone)
);

CREATE TABLE IF NOT EXISTS social_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    UNIQUE(run_id, page_url, profile_url)
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    image_url TEXT NOT NULL,
    UNIQUE(run_id, page_url, image_url)
);

CREATE TABLE IF NOT EXISTS javascript_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    asset_url TEXT NOT NULL,
    UNIQUE(run_id, page_url, asset_url)
);

CREATE TABLE IF NOT EXISTS technologies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    technology TEXT NOT NULL,
    UNIQUE(run_id, page_url, technology)
);

CREATE TABLE IF NOT EXISTS security_headers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    header_name TEXT NOT NULL,
    header_value TEXT NOT NULL,
    UNIQUE(run_id, page_url, header_name)
);

CREATE TABLE IF NOT EXISTS broken_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    broken_url TEXT NOT NULL,
    UNIQUE(run_id, page_url, broken_url)
);

CREATE TABLE IF NOT EXISTS intelligence_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    seed_url TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT NOT NULL,
    UNIQUE(run_id, finding_type, url)
);