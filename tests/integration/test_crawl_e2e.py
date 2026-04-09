import pytest

from app.crawlers.crawl_orchestrator import CrawlConfig, SiteCrawlOrchestrator


class FakeExtractor:
    def __init__(self, links_map):
        self.links_map = links_map

    async def start(self):
        return None

    async def close(self):
        return None

    async def extract_links(self, fetch_url: str, timeout_s: int):
        del timeout_s
        return list(self.links_map.get(fetch_url, []))


def _link(href: str, *, text: str = "", in_nav: bool = False, in_header_footer: bool = False):
    return {
        "href": href,
        "text": text,
        "in_nav": in_nav,
        "in_header_footer": in_header_footer,
    }


def _build_audit(score_by_url: dict[str, float], *, spa_urls: set[str] | None = None, blocked_urls: set[str] | None = None):
    spa_urls = spa_urls or set()
    blocked_urls = blocked_urls or set()

    async def audit(url: str, **kwargs):
        del kwargs
        if url in blocked_urls:
            raise PermissionError("403 forbidden")

        score = score_by_url.get(url, 90.0)
        return {
            "url": url,
            "issues": [],
            "score": score,
            "overall_score": score,
            "degraded_mode": False,
            "quality_gates": {"runtime_passed": True},
            "is_spa": url in spa_urls,
            "spa_framework": "react" if url in spa_urls else None,
        }

    return audit


@pytest.mark.asyncio
async def test_crawl_five_page_static_site_without_duplicates():
    seed = "https://example.com/"
    links_map = {
        seed: [
            _link("/login", text="Sign in"),
            _link("/about", in_nav=True),
            _link("/about#team", in_nav=True),
            _link("/docs"),
        ],
        "https://example.com/about": [_link("/contact", text="Contact")],
    }
    scores = {
        seed: 95.0,
        "https://example.com/login": 82.0,
        "https://example.com/about": 90.0,
        "https://example.com/docs": 88.0,
        "https://example.com/contact": 86.0,
    }

    orchestrator = SiteCrawlOrchestrator(
        audit_callable=_build_audit(scores),
        link_extractor=FakeExtractor(links_map),
        event_recorder=lambda event_type, payload: None,
    )
    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=5, max_depth=2, timeout_per_page_s=2, concurrency=1, await_enrichment=False),
    )

    urls = [row["url"] for row in result["page_summaries"]]
    assert result["pages_audited"] == 5
    assert len(urls) == len(set(urls))
    assert any(row["page_type"] == "interaction" for row in result["page_summaries"])
    assert result["site_score"] is not None


@pytest.mark.asyncio
async def test_crawl_spa_site_marks_spa_detection_per_page():
    seed = "https://spa.example.com/"
    links_map = {
        seed: [_link("/app"), _link("/help")],
    }
    scores = {
        seed: 90.0,
        "https://spa.example.com/app": 78.0,
        "https://spa.example.com/help": 88.0,
    }

    orchestrator = SiteCrawlOrchestrator(
        audit_callable=_build_audit(scores, spa_urls={"https://spa.example.com/app"}),
        link_extractor=FakeExtractor(links_map),
        event_recorder=lambda event_type, payload: None,
    )
    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=3, max_depth=1, timeout_per_page_s=2, concurrency=1, await_enrichment=False),
    )

    assert any(row["spa_detected"] for row in result["page_summaries"])


@pytest.mark.asyncio
async def test_crawl_respects_max_pages_three():
    seed = "https://example.com/"
    links_map = {
        seed: [_link("/a"), _link("/b"), _link("/c"), _link("/d")],
    }
    scores = {
        seed: 91.0,
        "https://example.com/a": 85.0,
        "https://example.com/b": 84.0,
        "https://example.com/c": 83.0,
        "https://example.com/d": 82.0,
    }

    orchestrator = SiteCrawlOrchestrator(
        audit_callable=_build_audit(scores),
        link_extractor=FakeExtractor(links_map),
        event_recorder=lambda event_type, payload: None,
    )
    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=3, max_depth=2, timeout_per_page_s=2, concurrency=1, await_enrichment=False),
    )

    assert result["pages_audited"] == 3


@pytest.mark.asyncio
async def test_crawl_completes_when_one_page_is_blocked():
    seed = "https://example.com/"
    blocked = {"https://example.com/blocked"}
    links_map = {
        seed: [_link("/blocked"), _link("/open")],
    }
    scores = {
        seed: 92.0,
        "https://example.com/open": 88.0,
    }

    orchestrator = SiteCrawlOrchestrator(
        audit_callable=_build_audit(scores, blocked_urls=blocked),
        link_extractor=FakeExtractor(links_map),
        event_recorder=lambda event_type, payload: None,
    )
    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=3, max_depth=2, timeout_per_page_s=2, concurrency=1, await_enrichment=False),
    )

    blocked_rows = [row for row in result["page_summaries"] if row["audit_status"] == "blocked"]
    assert blocked_rows
    assert result["crawl_status"] in {"partial", "completed"}
    assert result["crawl_status"] != "aborted"
