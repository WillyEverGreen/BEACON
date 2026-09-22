import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from app.services import audit_runner


def _minimal_issue(url: str) -> dict:
    return {
        "issue_id": "test-issue-1",
        "rule_id": "missing-alt",
        "issue_type": "violation",
        "element": "img.hero",
        "html_snippet": "<img src='hero.png'>",
        "page_url": url,
        "severity": "moderate",
        "wcag_criterion": "1.1.1",
        "wcag_level": "A",
        "category": "images",
        "confidence": 0.9,
        "confidence_sources": ["static"],
        "needs_manual_review": False,
        "description": "Image missing alt text",
        "suggested_fix": "Add alt text",
        "code_fix": "<img src='hero.png' alt='Hero'>",
        "fix_effort": "low",
        "group_id": "",
        "domain": "content",
        "evidence": {},
        "reproducibility": "",
    }


@pytest.fixture(autouse=True)
def _isolate_runner(monkeypatch):
    audit_runner._enrichment_tasks.clear()
    audit_runner._enriched_results.clear()

    # Unit tests use synthetic domains; bypass network-facing URL public checks.
    monkeypatch.setattr(audit_runner, "validate_public_url", lambda url: url)

    monkeypatch.setattr(audit_runner, "check_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(audit_runner, "save_to_cache", lambda *args, **kwargs: None)

    monkeypatch.setattr(audit_runner, "persist_audit_payload", lambda payload, status="completed": payload.get("audit_id", "test-audit-id"))
    monkeypatch.setattr(audit_runner, "persist_enrichment_payload", lambda *args, **kwargs: None)
    monkeypatch.setattr(audit_runner, "record_audit_event", lambda result, status="completed": {"audit_id": result.get("audit_id", "")})

    async def _noop_alerts(event):
        return []

    monkeypatch.setattr(audit_runner, "evaluate_audit_alerts", _noop_alerts)
    monkeypatch.setattr(audit_runner, "notify_llm_failure", lambda *args, **kwargs: None)


@pytest.mark.asyncio
async def test_wikipedia_like_static_site_returns_non_zero_score_and_valid_site_result(monkeypatch):
    async def _fake_fetch(url: str, timeout: float = 15.0):
        return "<html><head><title>Wikipedia</title></head><body><main>encyclopedia</main></body></html>", "", {}

    monkeypatch.setattr(audit_runner, "_fetch_html", _fake_fetch)
    monkeypatch.setattr(audit_runner.StaticChecker, "run_all", lambda self, checks=None: [])
    monkeypatch.setattr(audit_runner.HeuristicAnalyzer, "run_all", lambda self: [])

    result = await audit_runner.run_audit(
        url="https://www.wikipedia.org",
        scan_mode="fast",
        enable_enrichment=False,
        enable_cognitive=False,
    )

    assert result["score"] > 0
    assert result["score"] >= 90.0
    assert isinstance(result.get("issues"), list)
    assert isinstance(result.get("site_result"), dict)
    assert result["site_result"].get("pages_audited", 0) > 0
    assert result.get("pages_scanned", 0) > 0


@pytest.mark.asyncio
async def test_enrichment_failure_does_not_invalidate_base_audit(monkeypatch):
    async def _fake_fetch(url: str, timeout: float = 15.0):
        return "<html><head><title>Example</title></head><body><main><img src='hero.png'></main></body></html>", "", {}

    async def _fail_enrich(*args, **kwargs):
        raise RuntimeError("forced llm failure")

    monkeypatch.setattr(audit_runner, "_fetch_html", _fake_fetch)
    monkeypatch.setattr(audit_runner.StaticChecker, "run_all", lambda self, checks=None: [_minimal_issue("https://example.com")])
    monkeypatch.setattr(audit_runner.HeuristicAnalyzer, "run_all", lambda self: [])
    monkeypatch.setattr(audit_runner, "enrich_issues", _fail_enrich)

    result = await audit_runner.run_audit(
        url="https://example.com",
        scan_mode="fast",
        enable_enrichment=True,
        enable_cognitive=False,
    )

    assert result["score"] > 0
    assert result["total_issues"] >= 1
    assert isinstance(result["issues"], list)
    # Base audit remains valid and independent from async enrichment task outcome.
    assert result["enrichment_status"] == "pending"

    audit_id = result.get("audit_id")
    for _ in range(20):
        await asyncio.sleep(0.02)
        if audit_id in audit_runner._enriched_results:
            break

    assert audit_id in audit_runner._enriched_results
    assert audit_runner._enriched_results[audit_id]["status"] == "failed"


@pytest.mark.asyncio
async def test_empty_issue_set_never_defaults_to_zero_score(monkeypatch):
    async def _fake_fetch(url: str, timeout: float = 15.0):
        return "<html><head><title>No Issues</title></head><body><main>content</main></body></html>", "", {}

    monkeypatch.setattr(audit_runner, "_fetch_html", _fake_fetch)
    monkeypatch.setattr(audit_runner.StaticChecker, "run_all", lambda self, checks=None: [])
    monkeypatch.setattr(audit_runner.HeuristicAnalyzer, "run_all", lambda self: [])

    result = await audit_runner.run_audit(
        url="https://static.example.org",
        scan_mode="fast",
        enable_enrichment=False,
        enable_cognitive=False,
    )

    assert result["total_issues"] == 0
    assert result["score"] >= 90.0
    assert result["score"] != 0.0
    assert result.get("pages_scanned", 0) > 0


@pytest.mark.asyncio
async def test_max_mode_reports_phase_execution_and_playwright_invocation(monkeypatch):
    class _FakeBrowserProber:
        def __init__(self, url: str, timeout: int = 30000, max_retries: int = 2):
            self.url = url

        async def run_all(self, scan_mode: str = "deep"):
            assert scan_mode == "max"
            return (
                [_minimal_issue(self.url)],
                "<html><head><title>Max Mode</title></head><body><main>interactive</main></body></html>",
                {
                    "spa_framework": "react",
                    "is_spa": True,
                    "interaction_phase_ran": True,
                    "scroll_phase_ran": True,
                    "exploration_layer_ran": True,
                    "login_wall_detected": False,
                    "auth_fallback_attempted": False,
                    "auth_fallback_used": False,
                },
            )

    monkeypatch.setattr(audit_runner.StaticChecker, "run_all", lambda self, checks=None: [])
    monkeypatch.setattr(audit_runner.HeuristicAnalyzer, "run_all", lambda self: [])

    import app.services.browser_probes as browser_probes_module

    monkeypatch.setattr(browser_probes_module, "_PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(browser_probes_module, "BrowserProber", _FakeBrowserProber)

    result = await audit_runner.run_audit(
        url="https://max.example.org",
        scan_mode="max",
        enable_enrichment=False,
        enable_cognitive=False,
    )

    max_validation = result.get("quality_gates", {}).get("max_mode_validation", {})

    assert result["score"] > 0
    assert max_validation.get("playwright_invoked") is True
    assert max_validation.get("interaction_phase_ran") is True
    assert max_validation.get("scroll_phase_ran") is True
    assert max_validation.get("exploration_layer_ran") is True


@pytest.mark.asyncio
async def test_stale_poisoned_cache_entry_is_ignored_and_recomputed(monkeypatch):
    stale_cached = {
        "url": "https://static.example.org",
        "scan_mode": "fast",
        "total_issues": 0,
        "issues": [],
        "score": 0.0,
        "summary": "Failed to fetch URL: https://static.example.org",
        "enrichment_status": "failed",
        "pages_discovered": 0,
        "pages_audited": 0,
    }

    call_state = {"page_cache_calls": 0, "fetched": False}

    def _fake_cache_read(*args, **kwargs):
        tier = kwargs.get("tier", "page")
        if tier == "page" and call_state["page_cache_calls"] == 0:
            call_state["page_cache_calls"] += 1
            return stale_cached
        return None

    async def _fake_fetch(url: str, timeout: float = 15.0):
        call_state["fetched"] = True
        return "<html><head><title>Recomputed</title></head><body><main>ok</main></body></html>", "", {}

    monkeypatch.setattr(audit_runner, "check_cache", _fake_cache_read)
    monkeypatch.setattr(audit_runner, "_fetch_html", _fake_fetch)
    monkeypatch.setattr(audit_runner.StaticChecker, "run_all", lambda self, checks=None: [])
    monkeypatch.setattr(audit_runner.HeuristicAnalyzer, "run_all", lambda self: [])

    result = await audit_runner.run_audit(
        url="https://static.example.org",
        scan_mode="fast",
        enable_enrichment=False,
        enable_cognitive=False,
    )

    assert call_state["fetched"] is True
    assert result.get("cache_hit") is not True
    assert result["total_issues"] == 0
    assert result["score"] >= 90.0
    assert result["score"] != 0.0
    assert result["enrichment_status"] != "failed"
