from __future__ import annotations

import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .base import ExtractionContext

EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}"
    r"(?![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])"
)


class EmailExtractor:
    def extract(self, page_url: str, soup: BeautifulSoup, *, context: ExtractionContext) -> dict:
        emails: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if href.lower().startswith("mailto:"):
                mail_target = unquote(href.split(":", 1)[1]).split("?", 1)[0]
                normalized = self._normalize_email(mail_target)
                if normalized:
                    emails.add(normalized)

        text = soup.get_text(" ", strip=True)
        for match in EMAIL_RE.findall(text):
            normalized = self._normalize_email(match)
            if normalized:
                emails.add(normalized)

        return {"emails": sorted(emails)}

    def _normalize_email(self, email: str) -> str | None:
        cleaned = email.strip().lower().strip("<>\"'()[]{}.,;:!?")
        if not cleaned or "@" not in cleaned:
            return None

        local, _, domain = cleaned.partition("@")
        if not local or not domain:
            return None
        if ".." in local or ".." in domain:
            return None
        if "." not in domain:
            return None
        if not EMAIL_RE.fullmatch(cleaned):
            return None

        return f"{local}@{domain}"
