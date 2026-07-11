from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .base import CanonicalizeUrl, ExtractionContext, attribute_text

SOCIAL_DOMAINS = {
    "linkedin.com",
    "x.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "github.com",
}


class SocialExtractor:
    def __init__(self, canonicalize_url: CanonicalizeUrl) -> None:
        self._canonicalize_url = canonicalize_url

    def extract(self, page_url: str, soup: BeautifulSoup, *, context: ExtractionContext) -> dict:
        profiles: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = attribute_text(anchor.get("href")).strip()
            if not href or href.startswith("#"):
                continue

            absolute = self._canonicalize_url(urljoin(page_url, href))
            host = (urlsplit(absolute).hostname or "").lower()
            if any(host == dom or host.endswith(f".{dom}") for dom in SOCIAL_DOMAINS):
                profiles.add(absolute)

        return {"social_accounts": sorted(profiles)}
