import os
import sys
from dataclasses import dataclass
from typing import Any

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import app.services.audit_runner as audit_runner
from app.audit.failure_taxonomy import normalize_reason


@dataclass(frozen=True)
class Scenario:
    name: str
    expected_reason: str
    preflight_reason: str = "ok"
    browser_error: str | None = None
    fetch_html: str | None = None
    fetch_reason: str = ""
    fetch_status: int | None = None
    expect_html_incomplete: bool = False


SCENARIOS: list[Scenario] = [
    Scenario(
        name="dns_failure_connectivity_blocked",
        expected_reason="connectivity_blocked",
        preflight_reason="ok",
        browser_error="dns resolution failed",
        fetch_html=None,
        fetch_reason="connectivity_blocked",
    ),
    Scenario(
        name="http_429_rate_limited",
        expected_reason="rate_limited",
        preflight_reason="rate_limited",
        fetch_html=None,
        fetch_reason="rate_limited",
        fetch_status=429,
    ),
    Scenario(
        name="http_403_captcha_bot_wall",
        expected_reason="bot_wall",
        preflight_reason="bot_wall",
        fetch_html=None,
        fetch_reason="bot_wall",
        fetch_status=403,
    ),
    Scenario(
        name="csp_strict_header_blocked",
        expected_reason="csp_blocked",
        preflight_reason="csp_blocked",
        fetch_html="<html><body></body></html>",
        fetch_reason="",
        fetch_status=200,
        expect_html_incomplete=True,
    ),
    Scenario(
        name="csp_injection_failure",
        expected_reason="csp_injection_blocked",
        preflight_reason="csp_injection_blocked",
        fetch_html=None,
        fetch_reason="csp_injection_blocked",
    ),
    Scenario(
        name="navigation_timeout_browser_navigation_failed",
        expected_reason="browser_navigation_failed",
        preflight_reason="ok",
        browser_error="navigation timeout",
        fetch_html=None,
        fetch_reason="browser_navigation_failed",
    ),
    Scenario(
        name="partial_html_extraction_failed",
        expected_reason="extraction_failed",
        preflight_reason="ok",
        browser_error="dom parse extraction error",
        fetch_html=None,
        fetch_reason="extraction_failed",
    ),
]


@pytest.fixture(autouse=True)
def _isolate_runner(monkeypatch):
    audit_runner._enrichment_tasks.clear()
    audit_runner._enriched_results.clear()

    monkeypatch.setattr(audit_runner, "validate_public_url", lambda url: url)
    monkeypatch.setattr(audit_runner, "check_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(audit_runner, "save_to_cache", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        audit_runner,
        "persist_audit_payload",
        lambda payload, status="completed": payload.get("audit_id", "mode-consistency-audit"),
    )
    monkeypatch.setattr(audit_runner, "persist_enrichment_payload", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        audit_runner,
        "record_audit_event",
        lambda result, status="completed": {"audit_id": result.get("audit_id", "")},
    )

    async def _noop_alerts(event):
        return []

    monkeypatch.setattr(audit_runner, "evaluate_audit_alerts", _noop_alerts)
    monkeypatch.setattr(audit_runner, "notify_llm_failure", lambda *args, **kwargs: None)

    # Keep non-static engines deterministic and side-effect free.
    monkeypatch.setattr(audit_runner.HeuristicAnalyzer, "run_all", lambda self: [])


async def _run_modes_for_scenario(monkeypatch, scenario: Scenario) -> dict[str, dict[str, Any]]:
    import app.services.browser_probes as browser_probes

    class _FakeBrowserProber:
        def __init__(self, url: str, timeout: int = 30000, max_retries: int = 2):
            self.url = url
            self.timeout = timeout
            self.max_retries = max_retries

        async def run_all(self, scan_mode: str = "deep"):
            # Force axe path to skip after deep/max probe section runs.
            browser_probes._PLAYWRIGHT_AVAILABLE = False
            if scenario.browser_error:
                raise RuntimeError(scenario.browser_error)
            return [], None, {}

    async def _fake_preflight(url: str, *, run_id: str | None = None):
        reason = str(scenario.preflight_reason or "ok")
        status_code = scenario.fetch_status
        if reason == "rate_limited" and status_code is None:
            status_code = 429
        if reason == "bot_wall" and status_code is None:
            status_code = 403
        return audit_runner.PreflightResult(
            run_id=str(run_id or ""),
            domain="example.com",
            ok=(reason == "ok"),
            degraded_reason=reason,
            message="preflight_test",
            status_code=status_code,
            headers={},
            from_cache=False,
            fetch_meta={"status_code": status_code} if status_code is not None else {},
        )

    async def _fake_fetch_html(url: str, timeout: float = 15.0, **kwargs):
        del timeout, kwargs
        meta: dict[str, Any] = {}
        if scenario.fetch_status is not None:
            meta["status_code"] = int(scenario.fetch_status)
        return scenario.fetch_html, scenario.fetch_reason, meta

    monkeypatch.setattr(browser_probes, "BrowserProber", _FakeBrowserProber)
    monkeypatch.setattr(audit_runner, "_run_domain_preflight", _fake_preflight)
    monkeypatch.setattr(audit_runner, "_fetch_html", _fake_fetch_html)

    outputs: dict[str, dict[str, Any]] = {}
    for mode in ("fast", "deep", "max"):
        # Re-enable for each deep/max call so the fake prober path executes consistently.
        browser_probes._PLAYWRIGHT_AVAILABLE = True
        result = await audit_runner.run_audit(
            url="https://example.com/mode-consistency",
            scan_mode=mode,
            enable_enrichment=False,
            enable_cognitive=False,
            use_cache=False,
            run_id=f"mode-consistency::{scenario.name}",
        )
        outputs[mode] = result

    return outputs


def _fallback_category(result: dict[str, Any]) -> str:
    issues = list(result.get("issues") or [])
    if not issues:
        return "none"

    has_availability = any(
        str(issue.get("category") or "").strip().lower() == "availability"
        or str(issue.get("rule_id") or "").strip().lower()
        in {"fetch-unavailable", "blocked-request-partial", "beacon-availability-001"}
        for issue in issues
    )
    if has_availability:
        return "availability"
    return "structural"


def _html_incomplete_scoring(result: dict[str, Any]) -> Any:
    for issue in list(result.get("issues") or []):
        if str(issue.get("rule_id") or "").strip().lower() == "html-incomplete":
            return issue.get("scoring")
    return None


def _confidence_bucket(result: dict[str, Any]) -> str:
    score = float(result.get("confidence_score", 0.0) or 0.0)
    return "lt_0_3" if score < 0.3 else "gte_0_3"


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.name for s in SCENARIOS])
async def test_mode_consistency_gate(monkeypatch, scenario: Scenario):
    outputs = await _run_modes_for_scenario(monkeypatch, scenario)

    reasons = {mode: normalize_reason(res.get("degraded_reason")) for mode, res in outputs.items()}
    assert set(reasons.values()) == {scenario.expected_reason}, f"degraded_reason mismatch: {reasons}"

    fallback_categories = {mode: _fallback_category(res) for mode, res in outputs.items()}
    assert len(set(fallback_categories.values())) == 1, f"fallback_category mismatch: {fallback_categories}"

    confidence_buckets = {mode: _confidence_bucket(res) for mode, res in outputs.items()}
    assert len(set(confidence_buckets.values())) == 1, f"confidence bucket mismatch: {confidence_buckets}"

    html_incomplete_scoring = {mode: _html_incomplete_scoring(res) for mode, res in outputs.items()}
    present_values = [value for value in html_incomplete_scoring.values() if value is not None]
    if present_values:
        assert len(set(present_values)) == 1, f"html-incomplete scoring mismatch: {html_incomplete_scoring}"
        assert present_values[0] is False, f"html-incomplete scoring should be False: {html_incomplete_scoring}"

    # Confidence-score suppression invariant: when confidence < 0.3, score must be null.
    for mode, res in outputs.items():
        confidence_score = float(res.get("confidence_score", 0.0) or 0.0)
        if confidence_score < 0.3:
            assert res.get("score") is None, f"{mode}: score must be null when confidence<0.3"

    if scenario.expect_html_incomplete:
        assert any(_html_incomplete_scoring(res) is not None for res in outputs.values()), (
            "Expected at least one html-incomplete issue for this scenario"
        )
        assert all(
            (_html_incomplete_scoring(res) in (None, False)) for res in outputs.values()
        ), "Expected html-incomplete scoring to be False whenever emitted"
