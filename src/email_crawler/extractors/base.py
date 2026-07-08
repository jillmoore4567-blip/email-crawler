from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bs4 import BeautifulSoup


@dataclass(slots=True)
class ExtractionContext:
    seed_host: str


class PageExtractor(Protocol):
    def extract(
        self,
        page_url: str,
        soup: BeautifulSoup,
        *,
        context: ExtractionContext,
    ) -> dict:
        ...
