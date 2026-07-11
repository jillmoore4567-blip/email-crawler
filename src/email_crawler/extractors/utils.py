from __future__ import annotations

from numbers import Real
from typing import Any, Callable

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import AttributeValueList, Tag

from .base import ExtractionContext

CanonicalizeUrl = Callable[[str], str]


def _attr_str(value: str | AttributeValueList | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return " ".join(str(item) for item in value).strip()


def _tag_attr_str(tag: Tag, name: str) -> str:
    return _attr_str(tag.get(name))


def _float_value(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(default)
    if isinstance(value, Real):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return float(stripped)
        except ValueError:
            return default
    return default


def _int_value(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, Real):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(stripped)
        except ValueError:
            try:
                return int(float(stripped))
            except ValueError:
                return default
    return default


def _str_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, AttributeValueList):
        return [str(item) for item in value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return []
