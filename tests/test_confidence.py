"""
Unit tests for the confidence scoring engine.

Tests multi-signal confidence calculation, severity downgrade rules,
cross-engine agreement boosting, and manual review flagging.
"""
import os
import sys

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.confidence import (
    _calc_cross_engine_agreement,
    _calc_evidence_quality,
    _calc_signal_strength,
    _calc_source_reliability,
    _confidence_tier,
    apply_confidence_rules,
    calculate_confidence,
)

# ── Source Reliability ─────────────────────────────────────────

class TestSourceReliability:
    def test_empty_sources_returns_default(self):
        assert _calc_source_reliability([]) == 0.5

    def test_known_source_scores(self):
        score = _calc_source_reliability(["axe-core"])
        assert 0.0 <= score <= 1.0

    def test_multiple_sources_averaged(self):
        score = _calc_source_reliability(["axe-core", "heuristic"])
        assert 0.0 <= score <= 1.0

    def test_unknown_source_defaults_to_05(self):
        score = _calc_source_reliability(["unknown_engine"])
        assert score == 0.5


# ── Signal Strength ────────────────────────────────────────────

class TestSignalStrength:
    def test_violation_high_strength(self):
        issue = {"issue_type": "violation", "severity": "critical"}
        assert _calc_signal_strength(issue) >= 0.8

    def test_needs_review_low_strength(self):
        issue = {"issue_type": "needs-review", "severity": "moderate"}
        assert _calc_signal_strength(issue) < 0.6

    def test_minor_severity_penalty(self):
        issue_minor = {"issue_type": "violation", "severity": "minor"}
        issue_critical = {"issue_type": "violation", "severity": "critical"}
        assert _calc_signal_strength(issue_minor) < _calc_signal_strength(issue_critical)

    def test_unknown_type_defaults(self):
        issue = {"issue_type": "something_unknown", "severity": "moderate"}
        score = _calc_signal_strength(issue)
        assert 0.0 <= score <= 1.0


# ── Cross-Engine Agreement ────────────────────────────────────

class TestCrossEngineAgreement:
    def test_single_engine(self):
        assert _calc_cross_engine_agreement(["static"]) == 0.3

    def test_two_engines(self):
        assert _calc_cross_engine_agreement(["static", "heuristic"]) == 0.7

    def test_three_engines(self):
        assert _calc_cross_engine_agreement(["static", "heuristic", "axe-core"]) == 1.0

    def test_duplicate_sources_counted_once(self):
        # Two of the same should count as 1 unique
        assert _calc_cross_engine_agreement(["static", "static"]) == 0.3


# ── Evidence Quality ──────────────────────────────────────────

class TestEvidenceQuality:
    def test_full_evidence(self):
        issue = {
            "html_snippet": "<img>",
            "evidence": {"type": "visual"},
            "reproducibility": "always",
            "code_fix": "add alt attribute",
        }
        assert _calc_evidence_quality(issue) == 1.0

    def test_no_evidence(self):
        issue = {}
        assert _calc_evidence_quality(issue) == 0.0

    def test_partial_evidence(self):
        issue = {"html_snippet": "<img>"}
        score = _calc_evidence_quality(issue)
        assert 0.0 < score < 1.0


# ── Confidence Tiers ──────────────────────────────────────────

class TestConfidenceTier:
    def test_high_tier(self):
        assert _confidence_tier(0.9) == "high"

    def test_medium_tier(self):
        assert _confidence_tier(0.7) == "medium"

    def test_low_tier(self):
        assert _confidence_tier(0.3) == "low"

    def test_boundary_high(self):
        assert _confidence_tier(0.85) == "high"

    def test_boundary_medium(self):
        assert _confidence_tier(0.6) == "medium"


# ── Full Confidence Calculation ───────────────────────────────

class TestCalculateConfidence:
    def test_returns_float_in_range(self):
        issue = {
            "confidence_sources": ["static"],
            "issue_type": "violation",
            "severity": "critical",
            "html_snippet": "<img>",
        }
        score = calculate_confidence(issue)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_multi_engine_higher_than_single(self):
        single = {
            "confidence_sources": ["static"],
            "issue_type": "violation",
            "severity": "critical",
        }
        multi = {
            "confidence_sources": ["static", "heuristic", "axe-core"],
            "issue_type": "violation",
            "severity": "critical",
        }
        assert calculate_confidence(multi) > calculate_confidence(single)


# ── Apply Confidence Rules ────────────────────────────────────

class TestApplyConfidenceRules:
    def test_three_engines_auto_confirm(self):
        issues = [{
            "confidence_sources": ["static", "heuristic", "axe-core"],
            "issue_type": "violation",
            "severity": "critical",
            "rule_id": "missing-alt",
        }]
        result = apply_confidence_rules(issues)
        assert result[0]["confidence"] == 0.95

    def test_two_engines_floor_at_08(self):
        issues = [{
            "confidence_sources": ["static", "heuristic"],
            "issue_type": "violation",
            "severity": "critical",
            "rule_id": "missing-alt",
        }]
        result = apply_confidence_rules(issues)
        assert result[0]["confidence"] >= 0.8

    def test_heuristic_only_needs_review(self):
        issues = [{
            "confidence_sources": ["heuristic"],
            "issue_type": "violation",
            "severity": "moderate",
            "rule_id": "some-check",
        }]
        result = apply_confidence_rules(issues)
        assert result[0]["issue_type"] == "needs-review"
        assert result[0]["needs_manual_review"] is True

    def test_low_confidence_downgrades_severity(self):
        """Issues with very low confidence should get severity downgraded."""
        issues = [{
            "confidence_sources": [],
            "issue_type": "needs-review",
            "severity": "critical",
            "rule_id": "unknown-check",
        }]
        result = apply_confidence_rules(issues)
        # Low confidence should downgrade severity
        assert result[0]["confidence"] < 0.4
        assert result[0]["severity"] != "critical"

    def test_empty_issues_no_crash(self):
        result = apply_confidence_rules([])
        assert result == []

    def test_confidence_tier_attached(self):
        issues = [{
            "confidence_sources": ["axe-core"],
            "issue_type": "violation",
            "severity": "serious",
            "rule_id": "button-name",
        }]
        result = apply_confidence_rules(issues)
        assert "confidence_tier" in result[0]
        assert result[0]["confidence_tier"] in ("high", "medium", "low")
