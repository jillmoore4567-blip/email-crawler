from __future__ import annotations

from bs4 import BeautifulSoup

from .base import ExtractionContext


class MetadataExtractor:
    def extract(self, page_url: str, soup: BeautifulSoup, *, context: ExtractionContext) -> dict:
        title_node = soup.find("title")
        title = title_node.get_text(strip=True) if title_node else ""

        description = ""
        description_tag = soup.find("meta", attrs={"name": "description"})
        if description_tag:
            description = str(description_tag.get("content", "") or "").strip()

        keywords: list[str] = []
        keywords_tag = soup.find("meta", attrs={"name": "keywords"})
        if keywords_tag:
            raw = str(keywords_tag.get("content", "") or "").strip()
            if raw:
                keywords = [item.strip() for item in raw.split(",") if item.strip()]

        return {
            "title": title,
            "description": description,
            "keywords": keywords,
        }
