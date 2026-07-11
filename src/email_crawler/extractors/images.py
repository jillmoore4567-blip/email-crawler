from __future__ import annotations

from typing import Callable
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .base import ExtractionContext


class ImageExtractor:
    def __init__(self, canonicalize_url: Callable[[str], str]) -> None:
        self._canonicalize_url = canonicalize_url

    def extract(self, page_url: str, soup: BeautifulSoup, *, context: ExtractionContext) -> dict:
        images: set[str] = set()

        for image in soup.find_all("img"):
            raw_src = image.get("src")
            src = raw_src.strip() if isinstance(raw_src, str) else ""
            if not src:
                continue

            absolute = self._canonicalize_url(urljoin(page_url, src))
            parsed = urlsplit(absolute)
            if parsed.scheme not in {"http", "https"}:
                continue
            images.add(absolute)

        return {"images": sorted(images)}
