from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import ExtractionContext

PHONE_RE = re.compile(r"(?:(?<=\s)|^)(?:\+?\d[\d\s().\-]{6,}\d)(?=\s|$)")


class PhoneExtractor:
    def extract(self, page_url: str, soup: BeautifulSoup, *, context: ExtractionContext) -> dict:
        text = soup.get_text(" ", strip=True)
        phones: set[str] = set()
        for match in PHONE_RE.findall(text):
            normalized = self._normalize_phone(match)
            if normalized:
                phones.add(normalized)
        return {"phones": sorted(phones)}

    def _normalize_phone(self, raw: str) -> str | None:
        cleaned = re.sub(r"[^\d+]", "", raw)
        if cleaned.startswith("++"):
            return None
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) < 7 or len(digits) > 15:
            return None
        return cleaned
