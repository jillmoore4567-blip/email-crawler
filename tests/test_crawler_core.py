from __future__ import annotations

from bs4 import BeautifulSoup

from email_crawler.crawler import AsyncOsintCrawler, CrawlConfig, CrawlResult
from email_crawler.extractors import (
    DocumentExtractor,
    EmailExtractor,
    ImageExtractor,
    JavaScriptExtractor,
    LinkExtractor,
    MetadataExtractor,
    SocialExtractor,
    build_default_extractors,
)
from email_crawler.extractors.base import ExtractionContext
from email_crawler.io_utils import write_stats_json


def build_crawler() -> AsyncOsintCrawler:
    return AsyncOsintCrawler(CrawlConfig())


def test_url_canonicalization_removes_fragment_and_tracking_params() -> None:
    crawler = build_crawler()
    raw = "HTTPS://Example.com:443/a/./b/../c/?utm_source=x&b=2&a=1#fragment"
    got = crawler._canonicalize_url(raw)
    assert got == "https://example.com/a/c?a=1&b=2"


def test_page_finding_extracts_structured_osint() -> None:
    crawler = build_crawler()
    html = """
    <html>
      <head>
        <title>About Test</title>
        <meta name="description" content="Public profile and contacts" />
      </head>
      <body>
        Email us at admin@example.com
        Call +1 (555) 123-4567
        <a href="/contact">Contact</a>
        <a href="/files/report.pdf">Report</a>
        <a href="https://linkedin.com/company/example">LinkedIn</a>
      </body>
    </html>
    """
    finding = crawler._extract_page_finding("https://example.com/about", html, "example.com")

    assert finding.title == "About Test"
    assert finding.description == "Public profile and contacts"
    assert "Public profile and contacts" not in finding.keywords
    assert "admin@example.com" in finding.emails
    assert any("555" in phone for phone in finding.phones)
    assert "https://example.com/files/report.pdf" in finding.documents
    assert "https://linkedin.com/company/example" in finding.social_accounts
    assert "https://example.com/contact" in finding.internal_links


def test_domain_allowlist_blocks_non_allowed_hosts() -> None:
    crawler = AsyncOsintCrawler(CrawlConfig(allowed_domains=("example.com",)))
    assert crawler._is_allowed_domain("https://example.com/path", "seed.com")
    assert crawler._is_allowed_domain("https://sub.example.com/path", "seed.com")
    assert not crawler._is_allowed_domain("https://evil.com/path", "seed.com")


def test_duplicate_content_hash_detection_stable() -> None:
    crawler = build_crawler()
    html_a = "<html><body> Hello   world </body></html>"
    html_b = "<html><body>Hello world</body></html>"
    assert crawler._content_hash(html_a) == crawler._content_hash(html_b)


def test_extractor_registry_respects_javascript_toggle() -> None:
    def canonicalize(value: str) -> str:
        return value

    with_js = build_default_extractors(canonicalize, collect_javascript_assets=True)
    without_js = build_default_extractors(canonicalize, collect_javascript_assets=False)

    assert any(extractor.__class__.__name__ == "JavaScriptExtractor" for extractor in with_js)
    assert all(extractor.__class__.__name__ != "JavaScriptExtractor" for extractor in without_js)


def test_extractors_handle_list_like_attributes() -> None:
    soup = BeautifulSoup(
        """
        <html>
          <head>
            <meta name="description" />
            <meta name="keywords" />
          </head>
          <body>
            <a id="doc"></a>
            <a id="social"></a>
            <a id="contact"></a>
            <script></script>
            <img />
          </body>
        </html>
        """,
        "html.parser",
    )

    def canonicalize(value: str) -> str:
        return value.strip()

    context = ExtractionContext(seed_host="example.com")

    description_tag = soup.find("meta", attrs={"name": "description"})
    keywords_tag = soup.find("meta", attrs={"name": "keywords"})
    doc_link = soup.find("a", attrs={"id": "doc"})
    social_link = soup.find("a", attrs={"id": "social"})
    contact_link = soup.find("a", attrs={"id": "contact"})
    script_tag = soup.find("script")
    image_tag = soup.find("img")

    assert description_tag is not None
    assert keywords_tag is not None
    assert doc_link is not None
    assert social_link is not None
    assert contact_link is not None
    assert script_tag is not None
    assert image_tag is not None

    description_tag["content"] = [" Public ", "profile "]
    keywords_tag["content"] = ["alpha", ", beta"]
    doc_link["href"] = [" https://example.com/report.pdf "]
    social_link["href"] = [" https://github.com/example "]
    contact_link["href"] = [" mailto:Admin@Example.com "]
    script_tag["src"] = [" https://example.com/app.js "]
    image_tag["src"] = [" https://example.com/logo.png "]

    metadata = MetadataExtractor().extract("https://example.com", soup, context=context)
    documents = DocumentExtractor(canonicalize).extract("https://example.com", soup, context=context)
    social = SocialExtractor(canonicalize).extract("https://example.com", soup, context=context)
    emails = EmailExtractor().extract("https://example.com", soup, context=context)
    images = ImageExtractor(canonicalize).extract("https://example.com", soup, context=context)
    javascript = JavaScriptExtractor(canonicalize).extract("https://example.com", soup, context=context)
    links = LinkExtractor(canonicalize).extract("https://example.com", soup, context=context)

    assert metadata["description"] == "Public profile"
    assert metadata["keywords"] == ["alpha", "beta"]
    assert documents["documents"] == ["https://example.com/report.pdf"]
    assert social["social_accounts"] == ["https://github.com/example"]
    assert emails["emails"] == ["admin@example.com"]
    assert images["images"] == ["https://example.com/logo.png"]
    assert javascript["javascript_assets"] == ["https://example.com/app.js"]
    assert "https://example.com/report.pdf" in links["internal_links"]


def test_stats_include_observability_metrics(tmp_path) -> None:
    result = CrawlResult(seed_url="https://example.test")
    result.performance.fetch_time_seconds = 0.75
    result.performance.extraction_time_seconds = 0.25
    result.performance.requests_completed = 3
    result.performance.bytes_downloaded = 1500

    out = tmp_path / "stats.json"
    stats = write_stats_json([result], str(out))

    assert "performance" in stats
    assert stats["performance"]["aggregate"]["requests_completed"] == 3
    assert stats["performance"]["aggregate"]["avg_fetch_time_ms"] > 0
    assert stats["performance"]["per_seed"][0]["seed_url"] == "https://example.test"
