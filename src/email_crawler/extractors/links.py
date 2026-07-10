from __future__ import annotations

from typing import Callable
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .base import ExtractionContext


class LinkExtractor:
    def __init__(self, canonicalize_url: Callable[[str], str]) -> None:
        self._canonicalize_url = canonicalize_url

    def extract(self, page_url: str, soup: BeautifulSoup, *, context: ExtractionContext) -> dict:
        links: set[str] = set()
        internal: set[str] = set()
        external: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href", "") or "").strip()
            if not href or href.startswith("#"):
                continue

            absolute = self._canonicalize_url(urljoin(page_url, href))
            parsed = urlsplit(absolute)
            if parsed.scheme not in {"http", "https"}:
                continue

            links.add(absolute)
            host = (parsed.hostname or "").lower()
            if host == context.seed_host or host.endswith(f".{context.seed_host}"):
                internal.add(absolute)
            else:
                external.add(absolute)

        return {
            "links": sorted(links),
            "internal_links": sorted(internal),
            "external_links": sorted(external),
        }
