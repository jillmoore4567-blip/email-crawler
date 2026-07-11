from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .base import CanonicalizeUrl, ExtractionContext, attribute_text


class JavaScriptExtractor:
    def __init__(self, canonicalize_url: CanonicalizeUrl) -> None:
        self._canonicalize_url = canonicalize_url

    def extract(self, page_url: str, soup: BeautifulSoup, *, context: ExtractionContext) -> dict:
        assets: set[str] = set()

        for script in soup.find_all("script", src=True):
            src = attribute_text(script.get("src")).strip()
            if not src:
                continue
            absolute = self._canonicalize_url(urljoin(page_url, src))
            parsed = urlsplit(absolute)
            if parsed.scheme in {"http", "https"}:
                assets.add(absolute)

        return {"javascript_assets": sorted(assets)}