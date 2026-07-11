from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, TypeAlias

from bs4 import BeautifulSoup
from bs4.element import AttributeValueList


@dataclass(slots=True)
class ExtractionContext:
    seed_host: str


CanonicalizeUrl: TypeAlias = Callable[[str], str]
TagAttributeValue: TypeAlias = str | AttributeValueList | None


def attribute_text(value: TagAttributeValue) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return " ".join(part for part in (str(item).strip() for item in value) if part)


class PageExtractor(Protocol):
    def extract(
        self,
        page_url: str,
        soup: BeautifulSoup,
        *,
        context: ExtractionContext,
    ) -> dict:
        ...
