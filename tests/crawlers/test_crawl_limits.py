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
        return list(self.links_map.get(fetch_url, []))


def _link(href: str, *, text: str = "", in_nav: bool = False, in_header_footer: bool = False):
    return {
        "href": href,
        "text": text,
        "in_nav": in_nav,
        "in_header_footer": in_header_footer,
    }


async def _ok_audit(url: str, **kwargs):
    del kwargs
    return {
        "url": url,
        "issues": [],
        "score": 90.0,
        "overall_score": 90.0,
        "degraded_mode": False,
        "quality_gates": {"runtime_passed": True},
        "is_spa": False,
    }


@pytest.mark.asyncio
async def test_max_pages_respected_exactly():
    seed = "https://example.com/"
    extractor = FakeExtractor(
        {
            seed: [_link("/a"), _link("/b"), _link("/c")],
            "https://example.com/a": [_link("/d")],
            "https://example.com/b": [_link("/e")],
        }
    )
    orchestrator = SiteCrawlOrchestrator(
        audit_callable=_ok_audit,
        link_extractor=extractor,
        event_recorder=lambda event_type, payload: None,
    )

    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=3, max_depth=3, timeout_per_page_s=5, concurrency=1, await_enrichment=False),
    )

    assert result["pages_audited"] == 3


@pytest.mark.asyncio
async def test_max_depth_respected_exactly():
    seed = "https://example.com/"
    extractor = FakeExtractor(
        {
            seed: [_link("/contact")],
            "https://example.com/contact": [_link("/contact/child")],
            "https://example.com/contact/child": [_link("/contact/child/grand")],
        }
    )
    orchestrator = SiteCrawlOrchestrator(
        audit_callable=_ok_audit,
        link_extractor=extractor,
        event_recorder=lambda event_type, payload: None,
    )

    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=10, max_depth=1, timeout_per_page_s=5, concurrency=1, await_enrichment=False),
    )

    assert result["pages_audited"] == 2
    assert result["crawl_meta"]["pages_skipped_depth"] >= 1


def test_crawl_config_reads_runtime_values(monkeypatch):
    import app.config as config_mod

    monkeypatch.setattr(config_mod, "CRAWL_MAX_PAGES_PER_SITE", 21)
    monkeypatch.setattr(config_mod, "CRAWL_MAX_DEPTH", 4)
    monkeypatch.setattr(config_mod, "CRAWL_TIMEOUT_PER_PAGE_S", 41)
    monkeypatch.setattr(config_mod, "CRAWL_CONCURRENCY", 2)

    cfg = CrawlConfig.from_runtime_defaults()

    assert cfg.max_pages == 21
    assert cfg.max_depth == 4
    assert cfg.timeout_per_page_s == 41
    assert cfg.concurrency == 2


def test_deep_mode_hard_caps_are_enforced():
    cfg = CrawlConfig(
        max_pages=80,
        max_depth=6,
        timeout_per_page_s=60,
        concurrency=5,
        await_enrichment=False,
        scan_mode="deep",
    ).normalized()

    assert cfg.max_pages == 25
    assert cfg.max_depth == 3
    assert cfg.timeout_per_page_s == 15
    assert cfg.concurrency == 3


@pytest.mark.asyncio
async def test_adaptive_budget_reduces_under_failure_pressure():
    seed = "https://example.com/"

    async def mostly_failing(url: str, **kwargs):
        del kwargs
        if url.endswith("/ok"):
            return {
                "url": url,
                "issues": [],
                "score": 90.0,
                "overall_score": 90.0,
                "degraded_mode": False,
                "quality_gates": {"runtime_passed": True},
                "is_spa": False,
            }
        raise RuntimeError("navigation error")

    extractor = FakeExtractor(
        {
            seed: [_link("/a"), _link("/b"), _link("/ok"), _link("/c"), _link("/d")],
            "https://example.com/ok": [_link("/leaf")],
        }
    )

    orchestrator = SiteCrawlOrchestrator(
        audit_callable=mostly_failing,
        link_extractor=extractor,
        event_recorder=lambda event_type, payload: None,
    )

    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=12, max_depth=3, timeout_per_page_s=20, concurrency=3, await_enrichment=False),
    )

    assert result["crawl_meta"]["effective_max_pages"] <= 12
    assert result["crawl_meta"]["budget_reduction_events"] >= 0
    assert result["crawl_meta"]["failure_rate"] > 0


@pytest.mark.asyncio
async def test_low_information_gain_stops_crawl_early():
    seed = "https://example.com/"
    extractor = FakeExtractor(
        {
            seed: [_link("/a"), _link("/b"), _link("/c"), _link("/d"), _link("/e")],
        }
    )

    async def repetitive_issue(url: str, **kwargs):
        del kwargs
        return {
            "url": url,
            "issues": [
                {
                    "rule_id": "missing-label",
                    "issue_type": "missing-label",
                    "wcag_criterion": "3.3.2",
                    "selector": "#same",
                }
            ],
            "score": 88.0,
            "overall_score": 88.0,
            "degraded_mode": False,
            "quality_gates": {"runtime_passed": True},
            "is_spa": False,
        }

    orchestrator = SiteCrawlOrchestrator(
        audit_callable=repetitive_issue,
        link_extractor=extractor,
        event_recorder=lambda event_type, payload: None,
    )

    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(max_pages=10, max_depth=3, timeout_per_page_s=20, concurrency=2, await_enrichment=False),
    )

    assert result["crawl_meta"]["early_stop_reason"] in {"low_information_gain", "max_pages_reached", "adaptive_budget_reached"}


@pytest.mark.asyncio
async def test_standard_pages_are_skipped_when_budget_is_tight():
    seed = "https://example.com/"
    extractor = FakeExtractor(
        {
            seed: [
                _link("/form", text="Contact"),
                _link("/nav", in_nav=True),
                _link("/standard"),
            ]
        }
    )

    orchestrator = SiteCrawlOrchestrator(
        audit_callable=_ok_audit,
        link_extractor=extractor,
        event_recorder=lambda event_type, payload: None,
    )

    result = await orchestrator.crawl_site(
        seed,
        CrawlConfig(
            max_pages=3,
            max_depth=2,
            timeout_per_page_s=20,
            concurrency=2,
            await_enrichment=False,
            standard_page_skip_budget_threshold=2,
        ),
    )

    urls = [row["url"] for row in result["page_summaries"]]
    assert "https://example.com/standard" not in urls
