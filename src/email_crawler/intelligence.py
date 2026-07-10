from __future__ import annotations

import asyncio
import json
import re
import socket
import ssl
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urljoin, urlsplit

import aiohttp
from bs4 import BeautifulSoup


@dataclass(slots=True)
class IntelligenceFinding:
    finding_type: str
    url: str
    status: str
    details: dict

    def to_dict(self) -> dict:
        return {
            "finding_type": self.finding_type,
            "url": self.url,
            "status": self.status,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IntelligenceFinding":
        return cls(
            finding_type=str(data.get("finding_type", "")),
            url=str(data.get("url", "")),
            status=str(data.get("status", "")),
            details=dict(data.get("details", {})),
        )


class IntelligenceCollector:
    def __init__(self, canonicalize_url: Callable[[str], str]):
        self._canonicalize_url = canonicalize_url

    async def collect(
        self,
        session: aiohttp.ClientSession,
        seed_url: str,
        *,
        can_fetch: Callable[[str], Awaitable[bool]],
        obey_robots: bool,
        collect_robots: bool,
        collect_sitemap: bool,
        collect_security_txt: bool,
        collect_feeds: bool,
        collect_contact_pages: bool,
        collect_whois: bool,
        collect_tls: bool,
        collect_security_headers: bool,
        collect_tech_fingerprint: bool,
        collect_subdomains: bool,
        collect_screenshots: bool,
        screenshot_dir: str,
    ) -> list[IntelligenceFinding]:
        findings: list[IntelligenceFinding] = []
        parsed = urlsplit(seed_url)
        base = f"{parsed.scheme or 'https'}://{parsed.netloc}"
        host = (parsed.hostname or "").lower()
        port = parsed.port or (443 if (parsed.scheme or "https").lower() == "https" else 80)

        sitemap_urls: set[str] = set()
        homepage_text: str | None = None
        homepage_headers: dict[str, str] = {}

        if collect_robots:
            robots_url = self._canonicalize_url(urljoin(base, "/robots.txt"))
            robots_text, robots_status = await self._fetch_text(session, robots_url)
            if robots_text is not None:
                sitemaps = [
                    self._canonicalize_url(urljoin(base, raw_url))
                    for raw_url in self._extract_sitemaps_from_robots(robots_text)
                ]
                findings.append(
                    IntelligenceFinding(
                        finding_type="robots",
                        url=robots_url,
                        status=robots_status,
                        details={"sitemaps": sitemaps},
                    )
                )
                sitemap_urls.update(sitemaps)
            else:
                findings.append(
                    IntelligenceFinding(
                        finding_type="robots",
                        url=robots_url,
                        status=robots_status,
                        details={"sitemaps": []},
                    )
                )

        if collect_sitemap:
            sitemap_urls.add(self._canonicalize_url(urljoin(base, "/sitemap.xml")))
            for sitemap_url in sorted(sitemap_urls):
                if obey_robots and not await can_fetch(sitemap_url):
                    findings.append(
                        IntelligenceFinding(
                            finding_type="sitemap",
                            url=sitemap_url,
                            status="blocked_by_robots",
                            details={"urls": []},
                        )
                    )
                    continue

                text, status = await self._fetch_text(session, sitemap_url)
                if text is None:
                    findings.append(
                        IntelligenceFinding(
                            finding_type="sitemap",
                            url=sitemap_url,
                            status=status,
                            details={"urls": []},
                        )
                    )
                    continue

                urls = self._extract_urls_from_sitemap(text, sitemap_url)
                findings.append(
                    IntelligenceFinding(
                        finding_type="sitemap",
                        url=sitemap_url,
                        status=status,
                        details={"urls": urls[:500]},
                    )
                )

        if collect_security_txt:
            security_url = self._canonicalize_url(urljoin(base, "/.well-known/security.txt"))
            if not (obey_robots and not await can_fetch(security_url)):
                text, status = await self._fetch_text(session, security_url)
                if text is not None:
                    contacts = [
                        line.split(":", 1)[1].strip()
                        for line in text.splitlines()
                        if line.lower().startswith("contact:")
                    ]
                    findings.append(
                        IntelligenceFinding(
                            finding_type="security_txt",
                            url=security_url,
                            status=status,
                            details={"contacts": contacts[:50]},
                        )
                    )
                else:
                    findings.append(
                        IntelligenceFinding(
                            finding_type="security_txt",
                            url=security_url,
                            status=status,
                            details={"contacts": []},
                        )
                    )

        if collect_feeds:
            feed_candidates = {
                self._canonicalize_url(urljoin(base, "/feed")),
                self._canonicalize_url(urljoin(base, "/rss.xml")),
                self._canonicalize_url(urljoin(base, "/atom.xml")),
            }

            homepage_text, _ = await self._fetch_text(session, seed_url)
            if homepage_text:
                soup = BeautifulSoup(homepage_text, "html.parser")
                for link in soup.find_all("link", href=True):
                    rel = " ".join(link.get("rel") or []).lower()
                    type_attr = str(link.get("type", "") or "").lower()
                    if "alternate" in rel and ("rss" in type_attr or "atom" in type_attr or "xml" in type_attr):
                        href = str(link.get("href", "")).strip()
                        feed_candidates.add(self._canonicalize_url(urljoin(seed_url, href)))

            for feed_url in sorted(feed_candidates):
                if obey_robots and not await can_fetch(feed_url):
                    continue
                text, status = await self._fetch_text(session, feed_url)
                if text is None:
                    continue
                kind = "atom" if "<feed" in text[:300].lower() else "rss" if "<rss" in text[:300].lower() else "xml"
                findings.append(
                    IntelligenceFinding(
                        finding_type="feed",
                        url=feed_url,
                        status=status,
                        details={"feed_type": kind},
                    )
                )

        if collect_security_headers:
            headers, status = await self._fetch_headers(session, seed_url)
            homepage_headers = headers
            findings.append(
                IntelligenceFinding(
                    finding_type="security_headers",
                    url=seed_url,
                    status=status,
                    details={"headers": self._extract_security_headers(headers)},
                )
            )

        if collect_tech_fingerprint:
            if homepage_text is None:
                homepage_text, _ = await self._fetch_text(session, seed_url)
            if not homepage_headers:
                homepage_headers, _ = await self._fetch_headers(session, seed_url)
            findings.append(
                IntelligenceFinding(
                    finding_type="tech_fingerprint",
                    url=seed_url,
                    status="ok",
                    details={
                        "technologies": self._fingerprint_technologies(
                            homepage_text or "",
                            homepage_headers,
                        )
                    },
                )
            )

        if collect_whois and host:
            details, status = await self._collect_whois(session, host)
            findings.append(
                IntelligenceFinding(
                    finding_type="whois",
                    url=seed_url,
                    status=status,
                    details=details,
                )
            )

        if collect_tls and host and (parsed.scheme or "https").lower() == "https":
            details, status = await asyncio.to_thread(self._collect_tls, host, port)
            findings.append(
                IntelligenceFinding(
                    finding_type="tls_certificate",
                    url=seed_url,
                    status=status,
                    details=details,
                )
            )

        if collect_subdomains and host:
            details, status = await self._collect_subdomains(session, host)
            findings.append(
                IntelligenceFinding(
                    finding_type="subdomains",
                    url=seed_url,
                    status=status,
                    details=details,
                )
            )

        if collect_screenshots:
            screenshot_path, status = await self._capture_screenshot(seed_url, screenshot_dir)
            findings.append(
                IntelligenceFinding(
                    finding_type="screenshot",
                    url=seed_url,
                    status=status,
                    details={"path": screenshot_path or ""},
                )
            )

        if collect_contact_pages:
            contact_paths = ["/contact", "/contact-us", "/about/contact", "/support", "/help/contact"]
            for path in contact_paths:
                url = self._canonicalize_url(urljoin(base, path))
                if obey_robots and not await can_fetch(url):
                    continue
                text, status = await self._fetch_text(session, url)
                if text is None:
                    continue
                title = self._extract_title(text)
                findings.append(
                    IntelligenceFinding(
                        finding_type="contact_page",
                        url=url,
                        status=status,
                        details={"title": title},
                    )
                )

        # Remove duplicate findings by (type, url).
        dedup: dict[tuple[str, str], IntelligenceFinding] = {}
        for item in findings:
            dedup[(item.finding_type, item.url)] = item
        return list(dedup.values())

    async def _fetch_text(self, session: aiohttp.ClientSession, url: str) -> tuple[str | None, str]:
        try:
            async with session.get(url, allow_redirects=True) as response:
                if response.status >= 400:
                    return None, f"http_{response.status}"
                text = await response.text(errors="ignore")
                return text, "ok"
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None, "error"

    async def _fetch_headers(self, session: aiohttp.ClientSession, url: str) -> tuple[dict[str, str], str]:
        try:
            async with session.get(url, allow_redirects=True) as response:
                if response.status >= 400:
                    return {}, f"http_{response.status}"
                return dict(response.headers), "ok"
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return {}, "error"

    def _extract_sitemaps_from_robots(self, text: str) -> list[str]:
        urls: list[str] = []
        for line in text.splitlines():
            if line.lower().startswith("sitemap:"):
                urls.append(line.split(":", 1)[1].strip())
        return urls

    def _extract_urls_from_sitemap(self, text: str, base_url: str) -> list[str]:
        urls: list[str] = []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return urls

        ns_match = re.match(r"\{(.*)\}", root.tag)
        ns = {"sm": ns_match.group(1)} if ns_match else {}
        if ns:
            loc_path = ".//sm:loc"
        else:
            loc_path = ".//loc"

        for node in root.findall(loc_path, namespaces=ns):
            if node.text:
                urls.append(self._canonicalize_url(urljoin(base_url, node.text.strip())))
        return urls

    def _extract_title(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        title_node = soup.find("title")
        return title_node.get_text(strip=True) if title_node else ""

    async def _collect_whois(self, session: aiohttp.ClientSession, domain: str) -> tuple[dict, str]:
        rdap_url = f"https://rdap.org/domain/{domain}"
        try:
            async with session.get(rdap_url, allow_redirects=True) as response:
                if response.status >= 400:
                    return {"domain": domain}, f"http_{response.status}"
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError):
            return {"domain": domain}, "error"

        events = payload.get("events", []) if isinstance(payload, dict) else []
        created = ""
        updated = ""
        expires = ""
        for item in events:
            action = str(item.get("eventAction", "")).lower()
            date = str(item.get("eventDate", ""))
            if "registration" in action or "create" in action:
                created = created or date
            elif "last changed" in action or "update" in action:
                updated = updated or date
            elif "expiration" in action or "expire" in action:
                expires = expires or date

        nameservers = []
        for ns in payload.get("nameservers", []) if isinstance(payload, dict) else []:
            value = ns.get("ldhName")
            if value:
                nameservers.append(str(value))

        details = {
            "domain": domain,
            "handle": str(payload.get("handle", "")) if isinstance(payload, dict) else "",
            "status_list": payload.get("status", []) if isinstance(payload, dict) else [],
            "created": created,
            "updated": updated,
            "expires": expires,
            "nameservers": nameservers[:50],
        }
        return details, "ok"

    def _collect_tls(self, host: str, port: int) -> tuple[dict, str]:
        context = ssl.create_default_context()
        try:
            with socket.create_connection((host, port), timeout=8) as sock:
                with context.wrap_socket(sock, server_hostname=host) as tls_sock:
                    cert = tls_sock.getpeercert()
        except OSError:
            return {"host": host, "port": port}, "error"

        if cert is None:
            return {"host": host, "port": port}, "error"

        subject = self._extract_cert_name_pairs(cert.get("subject", []))
        issuer = self._extract_cert_name_pairs(cert.get("issuer", []))

        san_entries: list[str] = []
        for entry in cert.get("subjectAltName", []):
            if isinstance(entry, tuple) and len(entry) == 2:
                san_type, san_value = entry
                if str(san_type) == "DNS":
                    san_entries.append(str(san_value))

        details = {
            "host": host,
            "port": port,
            "subject_common_name": subject.get("commonName", ""),
            "issuer_common_name": issuer.get("commonName", ""),
            "not_before": cert.get("notBefore", ""),
            "not_after": cert.get("notAfter", ""),
            "san_dns": san_entries[:100],
        }
        return details, "ok"

    def _extract_cert_name_pairs(self, entries: object) -> dict[str, str]:
        pairs: dict[str, str] = {}
        if not isinstance(entries, tuple | list):
            return pairs

        for entry in entries:
            if isinstance(entry, tuple) and entry and isinstance(entry[0], tuple) and len(entry[0]) == 2:
                key, value = entry[0]
                pairs[str(key)] = str(value)
        return pairs

    async def _collect_subdomains(self, session: aiohttp.ClientSession, domain: str) -> tuple[dict, str]:
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        try:
            async with session.get(url, allow_redirects=True) as response:
                if response.status >= 400:
                    return {"domain": domain, "subdomains": []}, f"http_{response.status}"
                text = await response.text(errors="ignore")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return {"domain": domain, "subdomains": []}, "error"

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {"domain": domain, "subdomains": []}, "error"

        names: set[str] = set()
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                raw = str(item.get("name_value", "")).strip().lower()
                if not raw:
                    continue
                for part in raw.splitlines():
                    part = part.strip().lstrip("*.")
                    if part.endswith(domain) and part != domain:
                        names.add(part)

        subdomains = sorted(names)
        return {"domain": domain, "subdomains": subdomains[:300]}, "ok"

    async def _capture_screenshot(self, url: str, screenshot_dir: str) -> tuple[str | None, str]:
        try:
            from playwright.async_api import async_playwright  # type: ignore[import-not-found]
        except ImportError:
            return None, "dependency_missing"

        parsed = urlsplit(url)
        host = (parsed.hostname or "site").replace(".", "_")
        out_dir = Path(screenshot_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{host}.png"

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1440, "height": 900})
                await page.goto(url, wait_until="networkidle", timeout=20000)
                await page.screenshot(path=str(out_path), full_page=True)
                await browser.close()
        except Exception:
            return None, "error"

        return str(out_path), "ok"

    def _extract_security_headers(self, headers: dict[str, str]) -> dict[str, str]:
        if not headers:
            return {}

        normalized = {k.lower(): v for k, v in headers.items()}
        wanted = [
            "strict-transport-security",
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy",
            "permissions-policy",
        ]
        return {name: normalized[name] for name in wanted if name in normalized}

    def _fingerprint_technologies(self, html: str, headers: dict[str, str]) -> list[str]:
        detected: set[str] = set()
        lowered = html.lower()
        hdr = {k.lower(): v.lower() for k, v in headers.items()}

        server = hdr.get("server", "")
        powered = hdr.get("x-powered-by", "")

        if "cloudflare" in server or "cf-ray" in hdr:
            detected.add("Cloudflare")
        if "nginx" in server:
            detected.add("Nginx")
        if "apache" in server:
            detected.add("Apache")
        if "iis" in server:
            detected.add("IIS")
        if "php" in powered:
            detected.add("PHP")
        if "express" in powered:
            detected.add("Express")

        signatures = {
            "WordPress": ["/wp-content/", "wp-json"],
            "Drupal": ["drupal-settings-json", "sites/default/files"],
            "Joomla": ["/media/system/js/", "joomla"],
            "Shopify": ["cdn.shopify.com", "shopify.theme"],
            "React": ["react-dom", "__next", "data-reactroot"],
            "Next.js": ["/_next/", "__next"],
            "Vue": ["data-v-", "vue.js"],
            "Angular": ["ng-version", "angular"],
            "jQuery": ["jquery", "window.jquery"],
            "Bootstrap": ["bootstrap.min.css", "bootstrap.min.js"],
        }

        for name, markers in signatures.items():
            if any(marker in lowered for marker in markers):
                detected.add(name)

        return sorted(detected)
