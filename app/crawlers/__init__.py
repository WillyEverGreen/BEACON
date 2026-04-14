"""Crawler package for multi-page URL discovery.

This module intentionally uses lazy imports to avoid package-level import
cycles during application bootstrap.
"""

__all__ = [
    "BFSCrawler",
    "CrawlConfig",
    "CrawlerOrchestrator",
    "CrawledURL",
    "DOMCrawler",
    "SiteCrawlOrchestrator",
    "SitemapCrawler",
    "SitemapURL",
    "crawl_site",
]


def __getattr__(name: str):
    if name == "BFSCrawler":
        from app.crawlers.bfs_crawler import BFSCrawler

        return BFSCrawler

    if name in {"CrawlConfig", "SiteCrawlOrchestrator", "crawl_site"}:
        from app.crawlers.crawl_orchestrator import CrawlConfig, SiteCrawlOrchestrator, crawl_site

        return {
            "CrawlConfig": CrawlConfig,
            "SiteCrawlOrchestrator": SiteCrawlOrchestrator,
            "crawl_site": crawl_site,
        }[name]

    if name == "DOMCrawler":
        from app.crawlers.dom_crawler import DOMCrawler

        return DOMCrawler

    if name in {"CrawledURL", "SitemapURL"}:
        from app.crawlers.models import CrawledURL, SitemapURL

        return {
            "CrawledURL": CrawledURL,
            "SitemapURL": SitemapURL,
        }[name]

    if name == "SitemapCrawler":
        from app.crawlers.sitemap_crawler import SitemapCrawler

        return SitemapCrawler

    if name == "CrawlerOrchestrator":
        from app.crawlers.orchestrator import CrawlerOrchestrator

        return CrawlerOrchestrator

    raise AttributeError(f"module 'app.crawlers' has no attribute '{name}'")
