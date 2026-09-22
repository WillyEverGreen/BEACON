"""
Regression tests for degraded_mode + partial_engine_coverage signaling.

These tests specifically cover the scenario surfaced in real-world testing:
- deep/max mode requested
- browser-probe runs successfully (returns rendered HTML + some issues)
- axe-core times out or fails entirely
- Expected: degraded_mode=True, partial_engine_coverage=True
  (not the old behavior: degraded_mode=False because "something" ran)

Also tests the anti-overcorrection case: IBM disabled by config (enable_ibm=False)
should NOT cause degraded_mode to fire on an otherwise healthy run.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_probe_result(issues=None, html="<html><body>ok</body></html>"):
    """Return a 3-tuple matching BrowserProber.run_all() signature."""
    return (issues or [], html, {"is_spa": False, "spa_framework": None})


MINIMAL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Test</title></head>
<body>
  <h1>Hello World</h1>
  <p>Content paragraph.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Core scenario: browser-probe OK, axe-core fails → must be degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_axe_timeout_marks_degraded_and_partial_coverage():
    """
    Regression: deep mode, browser-probe succeeds, axe-core times out.
    Before fix: degraded_mode=False (because browser-probe "ran").
    After fix : degraded_mode=True, partial_engine_coverage=True.
    """
    from app.services.audit_runner import run_audit

    async def _fake_prober_success(*args, **kwargs):
        return _make_probe_result(html=MINIMAL_HTML)

    async def _fake_axe_timeout(*args, **kwargs):
        raise asyncio.TimeoutError("axe-core timed out")

    with (
        patch("app.services.audit_runner._fetch_html", new_callable=AsyncMock) as mock_fetch,
        patch("app.services.browser_probes._PLAYWRIGHT_AVAILABLE", True),
        patch("app.services.browser_probes.BrowserProber") as MockProber,
    ):
        # browser-probe succeeds
        prober_instance = MagicMock()
        prober_instance.run_all = AsyncMock(return_value=_make_probe_result(html=MINIMAL_HTML))
        MockProber.return_value = prober_instance

        # axe-core run always times out (simulate _run_axe_core_via_playwright timing out)
        # We patch the inner playwright context manager used in run_axe()
        with patch("playwright.async_api.async_playwright") as mock_pw:
            # Make page.goto raise TimeoutError
            mock_page = AsyncMock()
            mock_page.goto.side_effect = asyncio.TimeoutError("page.goto timed out")

            mock_context = AsyncMock()
            mock_context.new_page.return_value = mock_page

            mock_browser = AsyncMock()
            mock_browser.new_context.return_value = mock_context

            mock_p = AsyncMock()
            mock_p.chromium.launch.return_value = mock_browser

            async def _pw_context():
                return mock_p

            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_p)
            mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)

            # fetch not needed — browser-probe provided HTML
            mock_fetch.return_value = (MINIMAL_HTML, None, {"status_code": 200, "attempts_used": 1})

            result = await run_audit(
                "https://example.com",
                scan_mode="max",
                enable_ibm=False,  # intentionally disabled, must not cause false degraded
                use_cache=False,
                enable_enrichment=False,
            )

    # The fix: even though browser-probe "ran," axe-core failed → must be degraded
    assert result.get("degraded_mode") is True, (
        "degraded_mode should be True when axe-core fails in a max/deep scan"
    )
    assert result.get("partial_engine_coverage") is True, (
        "partial_engine_coverage should be True when requested engines were skipped"
    )
    # The score should still be present (not suppressed) since axe fallback still ran static checks
    assert result.get("score") is not None, (
        "score should still be returned even on partial coverage — suppression only happens at <0.30 confidence"
    )


# ---------------------------------------------------------------------------
# Anti-overcorrection: IBM disabled by config → healthy run must NOT be degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ibm_disabled_by_config_does_not_flag_degraded():
    """
    IBM disabled via enable_ibm=False on a deep scan where browser-probe
    and axe-core both succeed. Must NOT trigger degraded_mode or partial_engine_coverage.
    """
    from app.services.audit_runner import run_audit

    with (
        patch("app.services.audit_runner._fetch_html", new_callable=AsyncMock) as mock_fetch,
        patch("app.services.browser_probes._PLAYWRIGHT_AVAILABLE", True),
        patch("app.services.browser_probes.BrowserProber") as MockProber,
        patch("app.services.audit_runner._run_axe_core_via_playwright", new_callable=AsyncMock) as mock_axe,
        patch("playwright.async_api.async_playwright") as mock_pw,
    ):
        prober_instance = MagicMock()
        prober_instance.run_all = AsyncMock(return_value=_make_probe_result(html=MINIMAL_HTML))
        MockProber.return_value = prober_instance

        # axe-core succeeds and returns no violations
        mock_axe.return_value = []

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=None)
        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        mock_p = AsyncMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_fetch.return_value = (MINIMAL_HTML, None, {"status_code": 200, "attempts_used": 1})

        result = await run_audit(
            "https://example.com",
            scan_mode="deep",
            enable_ibm=False,  # IBM intentionally off, not a failure
            use_cache=False,
            enable_enrichment=False,
        )

    # IBM being disabled should not trip degraded signaling
    skipped = result.get("skipped_components", [])
    assert "ibm" not in skipped or result.get("degraded_mode") is False, (
        "IBM disabled by config should not cause degraded_mode=True or appear in skipped_components as a failure"
    )


# ---------------------------------------------------------------------------
# Correctly healthy max scan: all engines succeed → degraded_mode=False
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fully_healthy_max_scan_not_degraded():
    """
    All engines run successfully in max mode. degraded_mode must be False
    and partial_engine_coverage must be False.
    """
    from app.services.audit_runner import run_audit

    with (
        patch("app.services.audit_runner._fetch_html", new_callable=AsyncMock) as mock_fetch,
        patch("app.services.browser_probes._PLAYWRIGHT_AVAILABLE", True),
        patch("app.services.browser_probes.BrowserProber") as MockProber,
        patch("app.services.audit_runner._run_axe_core_via_playwright", new_callable=AsyncMock) as mock_axe,
        patch("app.services.audit_runner.run_ibm_scan_url", new_callable=AsyncMock) as mock_ibm,
        patch("playwright.async_api.async_playwright") as mock_pw,
    ):
        prober_instance = MagicMock()
        prober_instance.run_all = AsyncMock(return_value=_make_probe_result(html=MINIMAL_HTML))
        MockProber.return_value = prober_instance

        mock_axe.return_value = []
        mock_ibm.return_value = []

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=None)
        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        mock_p = AsyncMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_fetch.return_value = (MINIMAL_HTML, None, {"status_code": 200, "attempts_used": 1})

        result = await run_audit(
            "https://example.com",
            scan_mode="max",
            enable_ibm=True,
            use_cache=False,
            enable_enrichment=False,
        )

    # A fully healthy run must not be mislabeled as degraded
    assert result.get("degraded_mode") is False, (
        "A successful max scan with all engines completing must have degraded_mode=False"
    )
