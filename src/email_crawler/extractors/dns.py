from __future__ import annotations

import socket
from urllib.parse import urlsplit


class DNSExtractor:
    def __init__(self):
        self._cache: dict[str, list[str]] = {}

    def resolve_host(self, url: str) -> list[str]:
        host = (urlsplit(url).hostname or "").lower()
        if not host:
            return []
        if host in self._cache:
            return self._cache[host]

        try:
            _name, _aliases, addresses = socket.gethostbyname_ex(host)
            ips = sorted(set(addresses))
        except socket.gaierror:
            ips = []

        self._cache[host] = ips
        return ips
