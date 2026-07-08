from __future__ import annotations

from collections import OrderedDict
from typing import Callable

from .base import PageExtractor
from .documents import DocumentExtractor
from .emails import EmailExtractor
from .images import ImageExtractor
from .javascript_assets import JavaScriptExtractor
from .links import LinkExtractor
from .metadata import MetadataExtractor
from .phones import PhoneExtractor
from .social import SocialExtractor

ExtractorFactory = Callable[[Callable[[str], str]], PageExtractor]


class ExtractorRegistry:
    def __init__(self) -> None:
        self._factories: OrderedDict[str, ExtractorFactory] = OrderedDict()

    def register(self, name: str, factory: ExtractorFactory) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("Extractor plugin name cannot be empty")
        self._factories[key] = factory

    def unregister(self, name: str) -> None:
        self._factories.pop(name.strip().lower(), None)

    def names(self) -> tuple[str, ...]:
        return tuple(self._factories.keys())

    def build(
        self,
        canonicalize_url: Callable[[str], str],
        *,
        enabled: set[str] | None = None,
    ) -> list[PageExtractor]:
        enabled_set = {name.strip().lower() for name in (enabled or set()) if name.strip()}
        items: list[PageExtractor] = []
        for name, factory in self._factories.items():
            if enabled_set and name not in enabled_set:
                continue
            items.append(factory(canonicalize_url))
        return items


registry = ExtractorRegistry()


def register_builtin_extractors() -> None:
    # Registration order controls extraction merge precedence.
    registry.register("metadata", lambda canonicalize: MetadataExtractor())
    registry.register("links", lambda canonicalize: LinkExtractor(canonicalize))
    registry.register("emails", lambda canonicalize: EmailExtractor())
    registry.register("phones", lambda canonicalize: PhoneExtractor())
    registry.register("social", lambda canonicalize: SocialExtractor(canonicalize))
    registry.register("documents", lambda canonicalize: DocumentExtractor(canonicalize))
    registry.register("images", lambda canonicalize: ImageExtractor(canonicalize))
    registry.register("javascript_assets", lambda canonicalize: JavaScriptExtractor(canonicalize))


def build_default_extractors(
    canonicalize_url: Callable[[str], str],
    *,
    collect_javascript_assets: bool,
) -> list[PageExtractor]:
    enabled = set(registry.names())
    if not collect_javascript_assets:
        enabled.discard("javascript_assets")
    return registry.build(canonicalize_url, enabled=enabled)


register_builtin_extractors()
