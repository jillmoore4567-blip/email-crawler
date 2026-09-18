from __future__ import annotations

from bs4 import BeautifulSoup

from .base import ExtractionContext, attribute_text


class MetadataExtractor:
    def extract(self, page_url: str, soup: BeautifulSoup, *, context: ExtractionContext) -> dict:
        title_node = soup.find("title")
        title = title_node.get_text(strip=True) if title_node else ""

        description = ""
        description_tag = soup.find("meta", attrs={"name": "description"})
        if description_tag:
            description = attribute_text(description_tag.get("content")).strip()
            raw_description = description_tag.get("content")
            description = raw_description.strip() if isinstance(raw_description, str) else ""

        keywords: list[str] = []
        keywords_tag = soup.find("meta", attrs={"name": "keywords"})
        if keywords_tag:
            raw = attribute_text(keywords_tag.get("content")).strip()
            raw_content = keywords_tag.get("content")
            raw = raw_content.strip() if isinstance(raw_content, str) else ""
            if raw:
                keywords = [item.strip() for item in raw.split(",") if item.strip()]

        return {
            "title": title,
            "description": description,
            "keywords": keywords,
        }
