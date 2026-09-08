from __future__ import annotations

import re
from urllib.parse import urlparse

# Hosts that publish the statistic each topic settles on. Shared by discovery review and
# rule verification so both apply the same test (D-002: official data first).
OFFICIAL_SOURCE_HOSTS: dict[str, tuple[str, ...]] = {
    "cpi": ("bls.gov",),
    "unemployment": ("bls.gov",),
    "fed_rate": ("federalreserve.gov",),
    "gdp": ("bea.gov",),
}

_URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+")


def official_host(url: str, *, topic: str) -> str | None:
    """Return the matched official host for an https URL, or None when it is not official."""
    allowed = OFFICIAL_SOURCE_HOSTS.get(topic)
    if not allowed:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() != "https":
        return None
    host = (parsed.hostname or "").lower()
    for candidate in allowed:
        if host == candidate or host.endswith("." + candidate):
            return candidate
    return None


def is_official_source(url: str, *, topic: str) -> bool:
    return official_host(url, topic=topic) is not None


def extract_urls(text: str) -> tuple[str, ...]:
    """Return URLs in document order, trimmed of trailing punctuation."""
    found: list[str] = []
    for match in _URL_PATTERN.finditer(text):
        url = match.group(0).rstrip(".,;:")
        if url not in found:
            found.append(url)
    return tuple(found)


def first_official_url(text: str, *, topic: str) -> str | None:
    for url in extract_urls(text):
        if is_official_source(url, topic=topic):
            return url
    return None
