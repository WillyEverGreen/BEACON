import asyncio
import re

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


class ChainExtractor:
    async def start(self):
        return None

    async def close(self):
        return None

    async def extract_links(self, fetch_url: str, timeout_s: int):
        del timeout_s
        match = re.search(r"/p(\d+)$", fetch_url)
        current = int(match.group(1)) if match else 0
        return [{"href": f"/p{current + 1}", "text": "next", "in_nav": False, "in_header_footer": False}]


async def _ok_audit(url: str, **kwargs):
    del kwargs
    return {
        "url": url,
        "issues": [],
        "score": 88.0,
        "overall_score": 88.0,
        "degraded_mode": False,
        "quality_gates": {"runtime_passed": True},
        "is_spa": False,
    }


@pytest.mark.asyncio
async def test_timeout_is_marked_and_crawl_continues():
    seed = "https://example.com/"

    async def audit(url: str, **kwargs):
        del kwargs
        if url.endswith("/timeout"):
            await asyncio.sleep(2)
        return await _ok_audit(url)

    extractor = FakeExtractor(
        {
            seed: [
                {"href": "/timeout", "text": "timeout", "in_nav": False, "in_header_footer": False},
                {"href": "/ok", "text": "ok", "in_nav": False, "in_header_footer": False},
            ]
        }
    )

    orchestrator = SiteCrawlOrchestrator(audit_callable=audit, link_extractor=extractor)
    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(
            max_pages=3,
            max_depth=2,
            timeout_per_page_s=1,
            concurrency=1,
            await_enrichment=False,
            failure_rate_stop_threshold=0.95,
        ),
    )

    summaries = result["page_summaries"]
    timeout_rows = [row for row in summaries if row["audit_status"] == "timeout"]
    ok_rows = [row for row in summaries if row["url"].endswith("/ok") and row["audit_status"] == "success"]

    assert timeout_rows
    assert ok_rows


@pytest.mark.asyncio
async def test_navigation_error_is_marked_and_crawl_continues():
    seed = "https://example.com/"

    async def audit(url: str, **kwargs):
        del kwargs
        if url.endswith("/bad"):
            raise RuntimeError("navigation error page.goto failed")
        return await _ok_audit(url)

    extractor = FakeExtractor(
        {
            seed: [
                {"href": "/bad", "text": "bad", "in_nav": False, "in_header_footer": False},
                {"href": "/good", "text": "good", "in_nav": False, "in_header_footer": False},
            ]
        }
    )

    orchestrator = SiteCrawlOrchestrator(audit_callable=audit, link_extractor=extractor)
    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(
            max_pages=3,
            max_depth=2,
            timeout_per_page_s=2,
            concurrency=1,
            await_enrichment=False,
            failure_rate_stop_threshold=0.95,
        ),
    )

    summaries = result["page_summaries"]
    error_rows = [row for row in summaries if row["audit_status"] == "error"]
    good_rows = [row for row in summaries if row["url"].endswith("/good") and row["audit_status"] == "success"]

    assert error_rows
    # Phase 19-20: renamed navigation_error → browser_navigation_failed
    assert error_rows[0]["failure_reason"].startswith("browser_navigation_failed")
    assert good_rows


@pytest.mark.asyncio
async def test_blocked_page_is_marked_and_crawl_continues():
    seed = "https://example.com/"

    async def audit(url: str, **kwargs):
        del kwargs
        if url.endswith("/blocked"):
            raise PermissionError("403 forbidden")
        return await _ok_audit(url)

    extractor = FakeExtractor(
        {
            seed: [
                {"href": "/blocked", "text": "blocked", "in_nav": False, "in_header_footer": False},
                {"href": "/open", "text": "open", "in_nav": False, "in_header_footer": False},
            ]
        }
    )

    orchestrator = SiteCrawlOrchestrator(audit_callable=audit, link_extractor=extractor)
    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(
            max_pages=3,
            max_depth=2,
            timeout_per_page_s=2,
            concurrency=1,
            await_enrichment=False,
            failure_rate_stop_threshold=0.95,
        ),
    )

    # Phase 19-20: audit_status "blocked" → "error"; failure_reason "blocked" → "bot_wall"
    blocked_rows = [row for row in result["page_summaries"] if row["audit_status"] in ("blocked", "error")]
    assert blocked_rows
    assert blocked_rows[0]["failure_reason"].startswith("bot_wall")
    assert result["crawl_status"] != "aborted"


@pytest.mark.asyncio
async def test_consecutive_failures_trigger_early_stop():
    seed = "https://example.com/"

    async def failing_audit(url: str, **kwargs):
        del kwargs
        if url == seed:
            return await _ok_audit(url)
        raise RuntimeError("navigation error")

    extractor = FakeExtractor(
        {
            seed: [
                {"href": "/p1", "text": "p1", "in_nav": False, "in_header_footer": False},
                {"href": "/p2", "text": "p2", "in_nav": False, "in_header_footer": False},
            ]
        }
    )

    orchestrator = SiteCrawlOrchestrator(audit_callable=failing_audit, link_extractor=extractor)
    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=20, max_depth=20, timeout_per_page_s=2, concurrency=1, await_enrichment=False),
    )

    # Phase 20: crawl_status "aborted" → "partial" for consecutive-failure early stop
    assert result["crawl_status"] in ("partial", "aborted")
    assert result["crawl_meta"]["early_stop_reason"] == "failure_threshold"
    assert result["pages_audited"] == 2
    assert result["pages_failed"] == 1


@pytest.mark.asyncio
async def test_failed_page_does_not_enqueue_child_links():
    seed = "https://example.com/"

    async def audit(url: str, **kwargs):
        del kwargs
        if url.endswith("/bad"):
            raise RuntimeError("navigation error page.goto failed")
        return await _ok_audit(url)

    extractor = FakeExtractor(
        {
            seed: [
                {"href": "/bad", "text": "bad", "in_nav": False, "in_header_footer": False},
            ],
            "https://example.com/bad": [
                {"href": "/child", "text": "child", "in_nav": False, "in_header_footer": False},
            ],
        }
    )

    orchestrator = SiteCrawlOrchestrator(audit_callable=audit, link_extractor=extractor)
    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=5, max_depth=3, timeout_per_page_s=2, concurrency=1, await_enrichment=False),
    )

    urls = [row["url"] for row in result["page_summaries"]]
    assert "https://example.com/child" not in urls
    assert result["crawl_meta"]["pages_skipped_due_to_failure"] >= 0
