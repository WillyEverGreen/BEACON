"""
Unit tests for the schema compatibility adapter.

Validates field mapping between DJ HACK AuditIssue and DJ FR AccessibilityIssue,
disability group mapping from WCAG criteria, and checklist format compatibility.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schema_compat import (
    audit_issue_to_accessibility_issue,
    audit_issue_to_rag_finding,
    checklist_to_app_format,
    get_disability_groups,
    WCAG_DISABILITY_MAP,
)


# ── WCAG → Disability Group Mapping ──────────────────────────

class TestDisabilityGroupMapping:
    def test_perceivable_images(self):
        groups = get_disability_groups("1.1.1")
        assert "vision" in groups

    def test_operable_keyboard(self):
        groups = get_disability_groups("2.1.1")
        assert "motor" in groups

    def test_understandable_readable(self):
        groups = get_disability_groups("3.1.1")
        assert "cognitive" in groups

    def test_robust_compatible(self):
        groups = get_disability_groups("4.1.2")
        assert "vision" in groups

    def test_seizure_criterion(self):
        groups = get_disability_groups("2.3.1")
        assert "photosensitive" in groups

    def test_empty_criterion(self):
        groups = get_disability_groups("")
        assert groups == ["general"]

    def test_unknown_criterion(self):
        groups = get_disability_groups("99.99.99")
        assert groups == ["general"]


# ── AuditIssue → AccessibilityIssue ──────────────────────────

class TestAuditIssueMapping:
    @pytest.fixture
    def sample_issue(self):
        return {
            "rule_id": "missing-alt",
            "severity": "critical",
            "element": "img.hero",
            "description": "Image missing alt attribute",
            "wcag_criterion": "1.1.1",
            "wcag_level": "A",
            "suggested_fix": "Add descriptive alt text",
            "html_snippet": '<img src="hero.jpg">',
            "page_url": "https://example.com",
            "source": "static",
            "confidence": 0.9,
        }

    def test_css_selector_mapped(self, sample_issue):
        result = audit_issue_to_accessibility_issue(sample_issue)
        assert result["css_selector"] == "img.hero"

    def test_fix_suggestion_mapped(self, sample_issue):
        result = audit_issue_to_accessibility_issue(sample_issue)
        assert result["fix_suggestion"] == "Add descriptive alt text"

    def test_impact_mapped_from_severity(self, sample_issue):
        result = audit_issue_to_accessibility_issue(sample_issue)
        assert result["impact"] == "critical"

    def test_wcag_sc_mapped(self, sample_issue):
        result = audit_issue_to_accessibility_issue(sample_issue)
        assert result["wcag_sc"] == "1.1.1"

    def test_disability_groups_computed(self, sample_issue):
        result = audit_issue_to_accessibility_issue(sample_issue)
        assert "affected_disability_groups" in result
        assert "vision" in result["affected_disability_groups"]

    def test_passthrough_fields(self, sample_issue):
        result = audit_issue_to_accessibility_issue(sample_issue)
        assert result["html_snippet"] == '<img src="hero.jpg">'
        assert result["page_url"] == "https://example.com"
        assert result["confidence"] == 0.9

    def test_empty_issue(self):
        result = audit_issue_to_accessibility_issue({})
        assert result["rule_id"] == "unknown"
        assert result["css_selector"] == ""
        assert result["impact"] == "moderate"


# ── AuditIssue → RagFinding ──────────────────────────────────

class TestRagFindingMapping:
    def test_basic_mapping(self):
        issue = {
            "wcag_criterion": "2.4.4",
            "severity": "serious",
            "description": "Link text not descriptive",
            "element": "a.more-link",
            "page_url": "https://example.com/page",
            "suggested_fix": "Use descriptive link text",
        }
        result = audit_issue_to_rag_finding(issue)
        assert result["source"] == "rag"
        assert result["affected_element"] == "a.more-link"
        assert result["fix_suggestion"] == "Use descriptive link text"


# ── Checklist Format ─────────────────────────────────────────

class TestChecklistFormat:
    def test_basic_summary(self):
        check_results = {
            "html-lang": {"status": "pass", "detail": "OK"},
            "page-title": {"status": "fail", "detail": "Missing"},
            "meta-viewport": {"status": "warn", "detail": "Check"},
        }
        result = checklist_to_app_format(check_results)
        assert result["total_passed"] == 1
        assert result["total_failed"] == 1
        assert result["total_warnings"] == 1
        assert "score" in result
        assert 0 <= result["score"] <= 100

    def test_perfect_score(self):
        check_results = {
            "check-1": {"status": "pass", "detail": "OK"},
            "check-2": {"status": "pass", "detail": "OK"},
        }
        result = checklist_to_app_format(check_results)
        assert result["score"] == 100.0

    def test_zero_score(self):
        check_results = {
            "check-1": {"status": "fail", "detail": "Bad"},
        }
        result = checklist_to_app_format(check_results)
        assert result["score"] == 0.0

    def test_empty_results(self):
        result = checklist_to_app_format({})
        assert result["total_passed"] == 0
        assert result["total_failed"] == 0
        assert result["score"] == 100  # No checks = perfect

    def test_categories_grouping(self):
        check_results = {
            "html-lang": {"status": "pass", "detail": "OK"},
            "input-label": {"status": "fail", "detail": "Missing"},
        }
        categories = {
            "HTML & Structure": {"html-lang"},
            "Forms": {"input-label"},
        }
        result = checklist_to_app_format(check_results, categories)
        assert "HTML & Structure" in result["categories"]
        assert "Forms" in result["categories"]
        assert result["categories"]["HTML & Structure"]["passed"] == 1
        assert result["categories"]["Forms"]["failed"] == 1
