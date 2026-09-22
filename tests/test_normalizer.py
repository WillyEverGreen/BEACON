"""
Unit tests for the RAG pipeline tag module.

Tests WCAG SC extraction, issue type classification, user impact groups,
severity level detection, and topic extraction.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rag")))

from tag import tag_chunk

# ── WCAG SC Extraction ────────────────────────────────────────

class TestWCAGExtraction:
    def test_single_sc(self):
        chunk = {"text": "According to WCAG 1.1.1, all non-text content must have alt text."}
        result = tag_chunk(chunk)
        assert "1.1.1" in result["wcag_sc"]

    def test_multiple_sc(self):
        chunk = {"text": "Criteria 1.4.3 and 2.4.7 both relate to visibility of elements."}
        result = tag_chunk(chunk)
        assert "1.4.3" in result["wcag_sc"]
        assert "2.4.7" in result["wcag_sc"]

    def test_no_sc(self):
        chunk = {"text": "This is generic text about web design."}
        result = tag_chunk(chunk)
        assert result["wcag_sc"] == []


# ── Issue Type Classification ─────────────────────────────────

class TestIssueType:
    def test_images_classification(self):
        chunk = {"text": "All images must have alt text for non-text content accessibility."}
        result = tag_chunk(chunk)
        assert "images" in result["issue_types"]

    def test_keyboard_classification(self):
        chunk = {"text": "Keyboard focus must be visible on all interactive elements."}
        result = tag_chunk(chunk)
        assert "keyboard" in result["issue_types"]

    def test_forms_classification(self):
        chunk = {"text": "Each form input must have an associated label element."}
        result = tag_chunk(chunk)
        assert "forms" in result["issue_types"]

    def test_primary_type_first(self):
        chunk = {"text": "Keyboard focus on form input label elements."}
        result = tag_chunk(chunk)
        assert result["issue_type"] == result["issue_types"][0]

    def test_no_match_defaults_general(self):
        chunk = {"text": "Random unrelated content about cooking recipes."}
        result = tag_chunk(chunk)
        assert result["issue_type"] == "general"


# ── User Impact Groups ───────────────────────────────────────

class TestUserImpact:
    def test_blind_impact(self):
        chunk = {"text": "Screen reader users need proper alt text and ARIA roles."}
        result = tag_chunk(chunk)
        assert "blind" in result["user_impact"]

    def test_motor_impact(self):
        chunk = {"text": "Keyboard accessible controls with proper tabindex values."}
        result = tag_chunk(chunk)
        assert "motor" in result["user_impact"]

    def test_no_impact_defaults_general(self):
        chunk = {"text": "Random unrelated text with no accessibility keywords."}
        result = tag_chunk(chunk)
        assert result["user_impact"] == ["general"]


# ── Severity Detection ───────────────────────────────────────

class TestSeverity:
    def test_level_a(self):
        chunk = {"text": "This is a Level A requirement for conformance level a."}
        result = tag_chunk(chunk)
        assert result["severity"] == "A"

    def test_level_aa(self):
        chunk = {"text": "This criterion is (Level AA) conformance."}
        result = tag_chunk(chunk)
        assert result["severity"] == "AA"

    def test_level_aaa(self):
        chunk = {"text": "Level AAA requirements are the highest standard."}
        result = tag_chunk(chunk)
        assert result["severity"] == "AAA"

    def test_unknown_severity(self):
        chunk = {"text": "No level information present in this text."}
        result = tag_chunk(chunk)
        assert result["severity"] == "unknown"


# ── Topic Extraction ─────────────────────────────────────────

class TestTopic:
    def test_heading_extracted(self):
        chunk = {"text": "## Color Contrast Requirements\nSome content here."}
        result = tag_chunk(chunk)
        assert result["topic"] == "Color Contrast Requirements"

    def test_no_heading(self):
        chunk = {"text": "Just plain text without any heading markers."}
        result = tag_chunk(chunk)
        assert result["topic"] == ""

    def test_token_count(self):
        chunk = {"text": "one two three four five"}
        result = tag_chunk(chunk)
        assert result["token_count"] == 5
