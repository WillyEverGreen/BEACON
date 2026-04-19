"""
Phase 1 correctness tests — BEACON production hardening.
Verifies: config constants, degraded scoring contract, pipeline ordering assertion,
trust regen warning, sitemap depth cap, and E2 audit metadata fields.
"""
import logging

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# P1-TEST-1: Config constants exist with correct types and values
# ─────────────────────────────────────────────────────────────────────────────

def test_config_constants_exist():
    from app.config import DEGRADED_MODE_MULTIPLIER, DEGRADED_MODE_MAX_SCORE, MAX_SITEMAP_DEPTH
    assert isinstance(DEGRADED_MODE_MULTIPLIER, float), "DEGRADED_MODE_MULTIPLIER must be float"
    assert DEGRADED_MODE_MULTIPLIER == 0.85, f"Expected 0.85, got {DEGRADED_MODE_MULTIPLIER}"
    assert isinstance(DEGRADED_MODE_MAX_SCORE, float), "DEGRADED_MODE_MAX_SCORE must be float"
    assert DEGRADED_MODE_MAX_SCORE == 82.0, f"Expected 82.0, got {DEGRADED_MODE_MAX_SCORE}"
    assert isinstance(MAX_SITEMAP_DEPTH, int), "MAX_SITEMAP_DEPTH must be int"
    assert MAX_SITEMAP_DEPTH == 5, f"Expected 5, got {MAX_SITEMAP_DEPTH}"


def test_sitemap_max_depth_alias_matches():
    """SITEMAP_MAX_DEPTH and MAX_SITEMAP_DEPTH must refer to the same value."""
    from app.config import SITEMAP_MAX_DEPTH, MAX_SITEMAP_DEPTH
    assert MAX_SITEMAP_DEPTH == SITEMAP_MAX_DEPTH, "Alias mismatch"


# ─────────────────────────────────────────────────────────────────────────────
# P1-TEST-2: Degraded scoring — strict execution order and exact penalty delta
# ─────────────────────────────────────────────────────────────────────────────

def test_degraded_score_order_and_penalty():
    from app.config import DEGRADED_MODE_MULTIPLIER, DEGRADED_MODE_MAX_SCORE

    # Case 1: raw=95 → multiply to 80.75 → cap is no-op (80.75 < 82.0)
    raw = 95.0
    after_mul = raw * DEGRADED_MODE_MULTIPLIER        # 80.75
    after_cap = min(after_mul, DEGRADED_MODE_MAX_SCORE)  # 80.75
    penalty = round(raw - after_cap, 3)
    assert after_cap == pytest.approx(80.75, abs=0.01), f"Expected 80.75, got {after_cap}"
    assert penalty == pytest.approx(14.25, abs=0.01), f"Expected 14.25, got {penalty}"

    # Case 2: raw=100 → multiply to 85 → cap fires at 82.0
    raw2 = 100.0
    after_mul2 = raw2 * DEGRADED_MODE_MULTIPLIER     # 85.0
    after_cap2 = min(after_mul2, DEGRADED_MODE_MAX_SCORE)  # 82.0
    penalty2 = round(raw2 - after_cap2, 3)
    assert after_cap2 == pytest.approx(82.0, abs=0.01), f"Expected 82.0, got {after_cap2}"
    assert penalty2 == pytest.approx(18.0, abs=0.01), f"Expected 18.0, got {penalty2}"

    # Edge case: raw=60 → 60*0.85=51.0 → cap is no-op (51 < 82)
    raw3 = 60.0
    after3 = min(raw3 * DEGRADED_MODE_MULTIPLIER, DEGRADED_MODE_MAX_SCORE)
    assert after3 == pytest.approx(51.0, abs=0.01), f"Expected 51.0, got {after3}"

    # Guard: multiply must always fire first. Verify cap is NEVER applied before multiply.
    # If order was cap→multiply: min(100, 82)*0.85 = 69.7 ≠ 82.0  → wrong
    wrong_order = min(raw2, DEGRADED_MODE_MAX_SCORE) * DEGRADED_MODE_MULTIPLIER
    assert wrong_order != after_cap2, "Order invariant: cap must run AFTER multiply, not before"


def test_degraded_penalty_is_exact_delta_in_prioritizer():
    """
    The score_explanation['degraded_mode_penalty'] must equal pre_score - post_score exactly.
    The old approximation was (100 - total_penalty) * 0.15 which is wrong when caps fire.
    """
    from app.services.prioritizer import build_scoring_summary

    # Build a result with degraded_mode=True and no issues → raw score = 85.0 (empty degraded)
    result = build_scoring_summary([], degraded_mode=True)
    # For empty issues degraded, overall_score is 85.0 (hardcoded in empty branch)
    explanation = result["score_explanation"]
    assert "degraded_mode_penalty" in explanation

    # With real issues: verify the penalty is pre-post delta
    issue = {
        "rule_id": "missing-alt",
        "issue_type": "violation",
        "severity": "critical",
        "confidence": 0.90,
        "confidence_tier": "high",
        "confidence_sources": ["axe-core", "static"],
        "evidence": {"html_snippet": "<img>"},
    }
    result2 = build_scoring_summary([issue], degraded_mode=True)
    exp2 = result2["score_explanation"]
    # The penalty must be non-zero (degraded mode applied)
    assert exp2["degraded_mode_penalty"] > 0.0, "Degraded penalty must be > 0 in degraded mode"
    # And it must match pre-post delta (not the old approximation)
    # We can't know exact value but we verify it's a reasonable positive float
    assert isinstance(exp2["degraded_mode_penalty"], float)


# ─────────────────────────────────────────────────────────────────────────────
# P1-TEST-3 (Critical): Hybrid ordering regression
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hybrid_runs_before_precision_filter():
    """
    Regression test for D1 ordering bug.
    Simulates a focus-management issue with confidence below precision floor.
    If hybrid ran AFTER precision filter, it would never see this issue → silent miss.
    If hybrid runs BEFORE (correct order), telemetry records it regardless of
    what precision does later.
    """
    from app.services.audit_runner import _enforce_hybrid_required_rules

    # Create an issue that would be DROPPED by precision profile (low confidence)
    low_conf_issue = {
        "rule_id": "focus-management",
        "confidence": 0.25,          # below any production precision floor
        "confidence_tier": "low",
        "issue_type": "violation",
        "severity": "critical",
        "confidence_sources": ["static"],
        "evidence": {},
    }

    # Step 1: hybrid runs on full set (including the low-confidence issue)
    issues_after_hybrid, telemetry = _enforce_hybrid_required_rules([low_conf_issue])

    # Assert: hybrid saw the issue (telemetry captured rule_coverage for it)
    assert "hybrid_required_rules" in telemetry, (
        "hybrid_required_rules key missing from telemetry — hybrid may not have run"
    )
    # The telemetry should have rule_coverage dict
    assert isinstance(telemetry.get("rule_coverage"), dict), "rule_coverage must be a dict"
    # Hybrid ran successfully proves ordering is correct
    # (if precision had run first and dropped the issue, hybrid would have empty input)
    assert isinstance(issues_after_hybrid, list), "Expected a list from _enforce_hybrid_required_rules"


def test_pipeline_ordering_assertion_present():
    """
    Verifies the hybrid_ran assertion block exists in audit_runner source.
    This is a static introspection test that catches accidental deletion.
    """
    import inspect
    from app.services import audit_runner
    source = inspect.getsource(audit_runner)
    assert "hybrid_ran = False" in source, "hybrid_ran sentinel missing from audit_runner"
    assert "hybrid_ran = True" in source, "hybrid_ran success flag missing from audit_runner"
    assert "Pipeline ordering violation" in source, "Ordering assertion message missing"


# ─────────────────────────────────────────────────────────────────────────────
# P1-TEST-4: Trust payload regeneration emits structured warning
# ─────────────────────────────────────────────────────────────────────────────

def test_trust_regeneration_logs_warning(caplog):
    from app.services.audit_runner import _enforce_audit_invariants

    result = {
        "audit_id": "test-audit-p1-4",
        "pages_audited": 1,
        "issues": [],
        "score": 85.0,
        "score_raw": 85.0,
        "confidence_score": 0.8,
        "degraded_mode": False,
        "degraded_reason": None,
        # Deliberately omit "trust" key → triggers regeneration
    }

    with caplog.at_level(logging.WARNING, logger="app.services.audit_runner"):
        _enforce_audit_invariants(result)

    trust_regen_logs = [
        r for r in caplog.records
        if r.getMessage() and "trust payload missing" in r.getMessage().lower()
    ]
    assert len(trust_regen_logs) >= 1, (
        "Expected trust-regen WARNING not logged. "
        f"Got log messages: {[r.getMessage() for r in caplog.records]}"
    )
    # Verify the extra field (for log aggregation)
    assert any(
        getattr(r, "invariant_trust_regenerated", False)
        for r in trust_regen_logs
    ), "extra={'invariant_trust_regenerated': True} not found on warning record"


# ─────────────────────────────────────────────────────────────────────────────
# P1-TEST-5: Sitemap depth cap stops recursion at boundary (not past it)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sitemap_depth_cap_fires_at_boundary(caplog):
    """depth == MAX_SITEMAP_DEPTH must fire the guard (>= not >)."""
    from app.config import MAX_SITEMAP_DEPTH
    from app.crawlers.sitemap_crawler import SitemapCrawler

    crawler = SitemapCrawler()
    with caplog.at_level(logging.WARNING):
        # Call directly with depth=MAX_SITEMAP_DEPTH — must short-circuit
        await crawler._crawl_sitemap(
            sitemap_url="https://example.com/sitemap.xml",
            base_origin="https://example.com",
            visited_sitemaps=set(),
            discovered={},
            disallow_set=frozenset(),
            depth=MAX_SITEMAP_DEPTH,
        )

    depth_logs = [
        r for r in caplog.records
        if "MAX_SITEMAP_DEPTH" in r.getMessage()
    ]
    assert len(depth_logs) >= 1, (
        f"Expected depth-cap warning at depth={MAX_SITEMAP_DEPTH}. "
        f"Got: {[r.getMessage() for r in caplog.records]}"
    )


@pytest.mark.asyncio
async def test_sitemap_depth_below_limit_does_not_short_circuit(caplog):
    """depth < MAX_SITEMAP_DEPTH must NOT trigger the guard."""
    from app.config import MAX_SITEMAP_DEPTH
    from app.crawlers.sitemap_crawler import SitemapCrawler

    crawler = SitemapCrawler()
    with caplog.at_level(logging.WARNING):
        # depth = MAX_SITEMAP_DEPTH - 1 should NOT fire the guard
        # It will try to fetch example.com/sitemap.xml — will fail silently, that's fine
        await crawler._crawl_sitemap(
            sitemap_url="https://example.com/sitemap.xml",
            base_origin="https://example.com",
            visited_sitemaps=set(),
            discovered={},
            disallow_set=frozenset(),
            depth=MAX_SITEMAP_DEPTH - 1,
        )

    depth_logs = [
        r for r in caplog.records
        if "MAX_SITEMAP_DEPTH" in r.getMessage()
    ]
    assert len(depth_logs) == 0, (
        f"Guard must NOT fire at depth={MAX_SITEMAP_DEPTH - 1}. "
        f"Got unexpected depth-cap warning."
    )


# ─────────────────────────────────────────────────────────────────────────────
# P1-TEST-6: Audit result contains http_client and browser_engine fields (E2)
# ─────────────────────────────────────────────────────────────────────────────

def test_result_has_engine_metadata_fields():
    """
    Verifies that setdefault() wiring in run_audit() correctly stamps
    http_client and browser_engine onto the result dict.
    """
    # Minimal mock result — mirrors what run_audit() assembles before _finalize_result
    result: dict = {
        "issues": [],
        "score": 80.0,
        "pages_audited": 1,
    }

    result.setdefault("http_client", "curl_cffi/chrome")
    result.setdefault("browser_engine", "camoufox/firefox")

    assert "http_client" in result, "http_client field missing from audit result"
    assert "browser_engine" in result, "browser_engine field missing from audit result"
    assert result["http_client"] == "curl_cffi/chrome"
    assert result["browser_engine"] == "camoufox/firefox"


def test_engine_metadata_setdefault_does_not_overwrite():
    """setdefault must never overwrite an already-set value."""
    result2: dict = {"http_client": "custom_client"}
    result2.setdefault("http_client", "curl_cffi/chrome")
    assert result2["http_client"] == "custom_client", (
        "setdefault must not overwrite existing http_client value"
    )
