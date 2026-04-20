"""Unit tests for app/services/lighthouse_enricher.py"""
from __future__ import annotations

import pytest

from app.services.lighthouse_enricher import (
    merge_findings,
    select_urls_for_lighthouse,
)


# ── URL selection ─────────────────────────────────────────────────────────────

def test_select_urls_empty_input():
    assert select_urls_for_lighthouse([]) == []


def test_select_urls_homepage_always_first():
    urls = ["https://ex.com/about", "https://ex.com/", "https://ex.com/contact"]
    selected = select_urls_for_lighthouse(urls, max_urls=5)
    assert selected[0] == "https://ex.com/"


def test_select_urls_respects_max_urls():
    urls = [f"https://ex.com/page{i}" for i in range(20)]
    selected = select_urls_for_lighthouse(urls, max_urls=3)
    assert len(selected) <= 3


def test_select_urls_no_duplicates():
    urls = ["https://ex.com/"] * 10
    selected = select_urls_for_lighthouse(urls, max_urls=5)
    assert len(selected) == 1
    assert selected[0] == "https://ex.com/"


def test_select_urls_prioritizes_priority_pages():
    urls = [
        "https://ex.com/",
        "https://ex.com/about",
        "https://ex.com/blog",
        "https://ex.com/login",
        "https://ex.com/checkout",
    ]
    selected = select_urls_for_lighthouse(urls, max_urls=5)
    selected_lower = [u.lower() for u in selected]
    # Priority pages should be present when budget allows
    assert any("login" in u for u in selected_lower) or any("checkout" in u for u in selected_lower)


def test_select_urls_single_url():
    urls = ["https://ex.com/"]
    selected = select_urls_for_lighthouse(urls, max_urls=5)
    assert selected == ["https://ex.com/"]


# ── Merge findings ────────────────────────────────────────────────────────────

_BEACON_FINDING = {
    "rule_id": "color_contrast_insufficient",
    "severity": "moderate",
    "lighthouse_confirmed": False,
    "source": "beacon",
}

_LH_FINDING_SAME_KEY = {
    "rule_id": "color_contrast_insufficient",
    "lighthouse_score": 20,  # < 50 → serious trigger
    "severity": "serious",
    "source": "lighthouse",
    "confidence": "supplementary",
    "lighthouse_audit_id": "color-contrast",
}

_LH_FINDING_NEW_KEY = {
    "rule_id": "js_bundle_size",
    "lighthouse_score": 30,  # < 50 → supplementary
    "severity": "serious",
    "source": "lighthouse",
    "confidence": "supplementary",
    "lighthouse_audit_id": "unused-javascript",
}

_LH_FINDING_ADDITIONAL_INSIGHT = {
    "rule_id": "image_optimization",
    "lighthouse_score": 70,  # 50-89 → additional_insight
    "severity": "moderate",
    "source": "lighthouse",
    "confidence": "additional_insight",
    "lighthouse_audit_id": "uses-optimized-images",
}


def test_merge_rule1_beacon_confirmed():
    """Rule 1: Lighthouse confirms BEACON finding → lighthouse_confirmed=True."""
    enriched, telemetry = merge_findings([_BEACON_FINDING], [_LH_FINDING_SAME_KEY])
    assert telemetry["confirmed_count"] == 1
    beacon_out = next(f for f in enriched if f["source"] == "beacon")
    assert beacon_out["lighthouse_confirmed"] is True


def test_merge_rule1_severity_upgrade_when_score_below_50():
    """Rule 1 sub-rule: low LH score → severity upgraded one level."""
    beacon = dict(_BEACON_FINDING)
    beacon["severity"] = "moderate"
    enriched, telemetry = merge_findings([beacon], [_LH_FINDING_SAME_KEY])
    beacon_out = next(f for f in enriched if f.get("source") == "beacon")
    assert beacon_out["severity"] == "serious"
    assert beacon_out["severity_upgraded_by_lighthouse"] is True
    assert telemetry["severity_upgraded_count"] == 1


def test_merge_rule1_no_upgrade_when_score_50_or_above():
    """Rule 1: score >= 50 → severity unchanged."""
    lh_mid = dict(_LH_FINDING_SAME_KEY)
    lh_mid["lighthouse_score"] = 60  # ≥ 50
    beacon = dict(_BEACON_FINDING)
    beacon["severity"] = "moderate"
    enriched, telemetry = merge_findings([beacon], [lh_mid])
    beacon_out = next(f for f in enriched if f.get("source") == "beacon")
    assert beacon_out["severity"] == "moderate"
    assert beacon_out.get("severity_upgraded_by_lighthouse") is False
    assert telemetry["severity_upgraded_count"] == 0


def test_merge_rule2_new_supplementary_finding():
    """Rule 2: Lighthouse-only, score < 50 → added as supplementary."""
    enriched, telemetry = merge_findings([], [_LH_FINDING_NEW_KEY])
    assert len(enriched) == 1
    assert enriched[0]["source"] == "lighthouse"
    assert telemetry["new_supplementary_count"] == 1


def test_merge_rule3_new_additional_insight():
    """Rule 3: Lighthouse-only, score 50-89 → added as additional_insight."""
    enriched, telemetry = merge_findings([], [_LH_FINDING_ADDITIONAL_INSIGHT])
    assert len(enriched) == 1
    assert telemetry["new_additional_insight_count"] == 1


def test_merge_rule5_beacon_findings_never_deleted():
    """Rule 5: BEACON findings are never removed from enriched output."""
    beacon = dict(_BEACON_FINDING)
    lh_with_no_overlap = dict(_LH_FINDING_NEW_KEY)
    enriched, _ = merge_findings([beacon], [lh_with_no_overlap])
    beacon_out = [f for f in enriched if f.get("source") == "beacon"]
    assert len(beacon_out) == 1


def test_merge_beacon_findings_not_mutated_in_place():
    """merge_findings must not mutate the caller's input lists."""
    beacon = [dict(_BEACON_FINDING)]
    original_confirmed = beacon[0]["lighthouse_confirmed"]
    merge_findings(beacon, [_LH_FINDING_SAME_KEY])
    assert beacon[0]["lighthouse_confirmed"] == original_confirmed


def test_merge_empty_lighthouse_findings():
    """If Lighthouse finds nothing (all dropped by mapper), BEACON findings unchanged."""
    beacon = [dict(_BEACON_FINDING)]
    enriched, telemetry = merge_findings(beacon, [])
    assert len(enriched) == 1
    assert telemetry["confirmed_count"] == 0
    assert telemetry["new_supplementary_count"] == 0


def test_merge_critical_not_upgraded_beyond_critical():
    """Critical severity has no higher level — upgrade should be a no-op."""
    beacon = dict(_BEACON_FINDING)
    beacon["severity"] = "critical"
    enriched, telemetry = merge_findings([beacon], [_LH_FINDING_SAME_KEY])
    beacon_out = next(f for f in enriched if f.get("source") == "beacon")
    assert beacon_out["severity"] == "critical"
    # No upgrade should be recorded since severity didn't change.
    assert telemetry["severity_upgraded_count"] == 0
