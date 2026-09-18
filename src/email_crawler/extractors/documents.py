from __future__ import annotations

from typing import Callable
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .base import CanonicalizeUrl, ExtractionContext, attribute_text

DOC_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".csv",
}


class DocumentExtractor:
    def __init__(self, canonicalize_url: CanonicalizeUrl) -> None:
    def __init__(self, canonicalize_url: Callable[[str], str]) -> None:
        self._canonicalize_url = canonicalize_url

    def extract(self, page_url: str, soup: BeautifulSoup, *, context: ExtractionContext) -> dict:
        docs: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = attribute_text(anchor.get("href")).strip()
            raw_href = anchor.get("href")
            href = raw_href.strip() if isinstance(raw_href, str) else ""
            if not href or href.startswith("#"):
                continue

            absolute = self._canonicalize_url(urljoin(page_url, href))
            path = (urlsplit(absolute).path or "").lower()
            if any(path.endswith(ext) for ext in DOC_EXTENSIONS):
                docs.add(absolute)

        return {"documents": sorted(docs)}
