"""Unit tests for app/services/lighthouse_mapper.py"""
from __future__ import annotations

import json
import pytest

from app.services.lighthouse_mapper import (
    _normalize_score,
    _score_to_severity,
    extract_category_scores,
    map_lighthouse_report,
)


# ── Score normalization ───────────────────────────────────────────────────────

def test_normalize_score_zero():
    assert _normalize_score(0.0) == 0


def test_normalize_score_one():
    assert _normalize_score(1.0) == 100


def test_normalize_score_rounds():
    assert _normalize_score(0.555) == 56  # round(55.5) = 56


def test_normalize_score_none_returns_none():
    """Null raw score must remain None — never coerced to 0."""
    assert _normalize_score(None) is None


def test_normalize_score_half():
    assert _normalize_score(0.5) == 50


# ── Severity threshold mapping ────────────────────────────────────────────────

def test_severity_serious_below_50():
    assert _score_to_severity(0) == "serious"
    assert _score_to_severity(49) == "serious"


def test_severity_moderate_50_to_89():
    assert _score_to_severity(50) == "moderate"
    assert _score_to_severity(89) == "moderate"


def test_severity_none_at_90_plus():
    assert _score_to_severity(90) is None
    assert _score_to_severity(100) is None


def test_severity_none_for_null_score():
    """Null score → drop (informational audit)."""
    assert _score_to_severity(None) is None


# ── Category score extraction ─────────────────────────────────────────────────

def test_extract_category_scores_present():
    raw = {
        "categories": {
            "performance": {"score": 0.75},
            "accessibility": {"score": 0.92},
            "seo": {"score": 0.60},
            "best-practices": {"score": 0.80},
        }
    }
    scores = extract_category_scores(raw)
    assert scores["performance"] == 75
    assert scores["accessibility"] == 92
    assert scores["seo"] == 60
    assert scores["best_practices"] == 80


def test_extract_category_scores_missing_returns_none():
    scores = extract_category_scores({})
    assert scores["performance"] is None
    assert scores["accessibility"] is None


def test_extract_category_scores_null_score():
    raw = {"categories": {"performance": {"score": None}}}
    scores = extract_category_scores(raw)
    assert scores["performance"] is None


# ── map_lighthouse_report ─────────────────────────────────────────────────────

def test_map_drops_audits_not_in_mapping():
    raw = {
        "audits": {
            "not-in-mapping": {
                "score": 0.1,
                "scoreDisplayMode": "binary",
                "title": "Some audit",
                "description": "desc",
            }
        }
    }
    findings = map_lighthouse_report(raw, page_url="https://x.com")
    assert findings == []


def test_map_emits_serious_finding_for_low_score():
    raw = {
        "audits": {
            "color-contrast": {
                "score": 0.2,  # → 20 → serious
                "scoreDisplayMode": "binary",
                "title": "Color contrast",
                "description": "desc",
            }
        }
    }
    findings = map_lighthouse_report(raw, page_url="https://x.com")
    assert len(findings) == 1
    assert findings[0]["severity"] == "serious"
    assert findings[0]["rule_id"] == "color_contrast_insufficient"
    assert findings[0]["lighthouse_score"] == 20


def test_map_emits_moderate_finding_for_mid_score():
    raw = {
        "audits": {
            "color-contrast": {
                "score": 0.7,  # → 70 → moderate
                "scoreDisplayMode": "binary",
                "title": "Color contrast",
                "description": "desc",
            }
        }
    }
    findings = map_lighthouse_report(raw, page_url="https://x.com")
    assert len(findings) == 1
    assert findings[0]["severity"] == "moderate"


def test_map_drops_high_score_silently():
    raw = {
        "audits": {
            "color-contrast": {
                "score": 0.95,  # → 95 → drop
                "scoreDisplayMode": "binary",
                "title": "Color contrast",
                "description": "desc",
            }
        }
    }
    findings = map_lighthouse_report(raw, page_url="https://x.com")
    assert findings == []


def test_map_drops_informational_audit():
    raw = {
        "audits": {
            "color-contrast": {
                "score": None,
                "scoreDisplayMode": "informative",
                "title": "Color contrast informational",
                "description": "desc",
            }
        }
    }
    findings = map_lighthouse_report(raw, page_url="https://x.com")
    assert findings == []


def test_map_sets_correct_source():
    raw = {
        "audits": {
            "html-has-lang": {
                "score": 0.0,
                "scoreDisplayMode": "binary",
                "title": "HTML lang",
                "description": "desc",
            }
        }
    }
    findings = map_lighthouse_report(raw, page_url="https://x.com")
    assert len(findings) == 1
    assert findings[0]["source"] == "lighthouse"


def test_map_score_conversion_single_place():
    """Score normalization must happen ONCE in mapper. Finding score is 0-100 int."""
    raw = {
        "audits": {
            "color-contrast": {
                "score": 0.33,
                "scoreDisplayMode": "binary",
                "title": "t",
                "description": "d",
            }
        }
    }
    findings = map_lighthouse_report(raw, page_url="https://x.com")
    assert findings[0]["lighthouse_score"] == 33
    assert isinstance(findings[0]["lighthouse_score"], int)
