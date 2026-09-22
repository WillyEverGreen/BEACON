"""Data models shared by crawler modules."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SitemapURL:
    """Canonical URL discovered from sitemap metadata."""

    url: str
    priority: float = 0.5
    changefreq: str = "unknown"
    lastmod: str | None = None
    depth: int = 0
    source: str = "sitemap"


@dataclass(slots=True)
class CrawledURL:
    """URL discovered through Discovery or DOM crawling."""

    url: str
    source: str
    depth: int = 0
    discovered_from: str | None = None
    state: str | None = None
    priority: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
