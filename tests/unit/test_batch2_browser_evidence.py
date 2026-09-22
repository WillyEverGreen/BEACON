"""
Unit tests for Batch 2: Browser Evidence & Interaction (§8–§16).
Verifies:
- §8: extract_element_evidence
- §9: capture_a11y_tree_evidence and DOM/a11y discrepancy detection
- §10: trace_keyboard_navigation and trap detection
- §11: analyze_focus_obscurance (2.4.11 / 2.4.12)
- §12: analyze_target_size and spacing/inline exceptions (2.5.8)
- §13: analyze_dragging_movements (2.5.7)
- §14: analyze_accessible_authentication (3.3.8 / 3.3.9)
- §15: evaluate_consistent_help (3.2.6)
- §16: evaluate_redundant_entry (3.3.7)
"""

from unittest.mock import AsyncMock

import pytest

from app.services.browser_evidence import (
    analyze_accessible_authentication,
    analyze_dragging_movements,
    analyze_focus_obscurance,
    analyze_target_size,
    capture_a11y_tree_evidence,
    evaluate_consistent_help,
    evaluate_redundant_entry,
    extract_element_evidence,
    trace_keyboard_navigation,
)


@pytest.mark.asyncio
class TestBatch2BrowserEvidence:

    async def test_extract_element_evidence(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = {
            "outerHTML": "<button id='submit'>Send</button>",
            "textContent": "Send",
            "bounding_rect": {"x": 100, "y": 200, "width": 80, "height": 40, "top": 200, "bottom": 240},
            "computed_styles": {"display": "inline-block", "visibility": "visible", "opacity": "1"},
            "viewport": {"width": 1280, "height": 800, "scrollX": 0, "scrollY": 0},
            "aria_attributes": {"aria-label": "Submit form"},
            "role": "button",
            "focus_state": {"is_active": True, "tabIndex": 0, "is_focusable": True},
            "ancestors": ["form#contact", "main", "body"],
            "nearest_landmark": "main",
        }

        res = await extract_element_evidence(mock_page, "#submit")
        assert res["role"] == "button"
        assert res["nearest_landmark"] == "main"
        assert res["bounding_rect"]["width"] == 80
        assert res["focus_state"]["is_focusable"] is True

    async def test_capture_a11y_tree_evidence_with_discrepancy(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = {
            "role": "button",
            "name": "",  # Empty computed name
            "value": None,
            "checked": None,
            "expanded": None,
            "disabled": True,
            "focused": True,  # Discrepancy: marked disabled but holds focus!
            "orientation": None,
            "level": None,
        }

        res = await capture_a11y_tree_evidence(mock_page, "#broken-btn")
        assert res["available"] is True
        assert res["has_discrepancy"] is True
        assert len(res["discrepancies"]) == 2  # disabled+focused, and empty accessible name

    async def test_trace_keyboard_navigation(self):
        mock_page = AsyncMock()
        mock_page.evaluate.side_effect = [
            {"selector": "a#skip-nav", "tag": "a", "focus_visible": True, "rect": {"x": 10, "y": 10, "width": 100, "height": 30}},
            {"selector": "nav a.link", "tag": "a", "focus_visible": True, "rect": {"x": 50, "y": 10, "width": 80, "height": 30}},
            {"selector": "input#search", "tag": "input", "focus_visible": False, "rect": {"x": 200, "y": 10, "width": 150, "height": 30}},
        ]

        trace = await trace_keyboard_navigation(mock_page, max_steps=3)
        assert trace["interaction"] == "keyboard_navigation"
        assert trace["total_steps"] == 3
        assert trace["trap_detected"] is False
        assert trace["steps"][0]["focused_selector"] == "a#skip-nav"

    async def test_focus_obscured_material_and_partial(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = [
            {
                "selector": "button#cta",
                "html": "<button id='cta'>Sign Up</button>",
                "obscuring_element": "header#sticky-nav",
                "overlap_percentage": 95,
                "classification": "material_overlap",
                "target_rect": {"width": 100, "height": 40},
                "viewport": {"width": 1280, "height": 800},
            },
            {
                "selector": "input#newsletter",
                "html": "<input id='newsletter'>",
                "obscuring_element": "div#cookie-banner",
                "overlap_percentage": 40,
                "classification": "partial_overlap",
                "target_rect": {"width": 200, "height": 40},
                "viewport": {"width": 1280, "height": 800},
            },
        ]

        issues = await analyze_focus_obscurance(mock_page, "https://example.com")
        assert len(issues) == 2
        
        # 2.4.11 Minimum AA violation for material overlap
        issue_aa = [i for i in issues if i["rule_id"] == "focus-obscured-minimum"][0]
        assert issue_aa["wcag_criterion"] == "2.4.11"
        assert issue_aa["wcag_level"] == "AA"
        
        # 2.4.12 Enhanced AAA violation for partial overlap
        issue_aaa = [i for i in issues if i["rule_id"] == "focus-obscured-enhanced"][0]
        assert issue_aaa["wcag_criterion"] == "2.4.12"
        assert issue_aaa["wcag_level"] == "AAA"

    async def test_target_size_and_exceptions(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = [
            # Target too small without clearance
            {
                "selector": "button#icon",
                "html": "<button id='icon'>x</button>",
                "width": 16,
                "height": 16,
                "is_inline_exception": False,
                "has_spacing_clearance": False,
            },
            # Inline text link exception
            {
                "selector": "a.footnote",
                "html": "<a class='footnote'>[1]</a>",
                "width": 14,
                "height": 14,
                "is_inline_exception": True,
                "has_spacing_clearance": False,
            },
            # Clearance satisfied exception
            {
                "selector": "button#isolated",
                "html": "<button id='isolated'>+</button>",
                "width": 18,
                "height": 18,
                "is_inline_exception": False,
                "has_spacing_clearance": True,
            },
        ]

        issues = await analyze_target_size(mock_page, "https://example.com")
        assert len(issues) == 1
        assert issues[0]["rule_id"] == "target-size-minimum"
        assert issues[0]["wcag_criterion"] == "2.5.8"
        assert issues[0]["element"] == "button#icon"

    async def test_dragging_movements_analysis(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = [
            {"selector": "div#kanban-card", "type": "draggable_attribute", "html": "<div draggable='true'></div>"}
        ]

        issues = await analyze_dragging_movements(mock_page, "https://example.com")
        assert len(issues) == 1
        assert issues[0]["rule_id"] == "dragging-movements-alternative"
        assert issues[0]["wcag_criterion"] == "2.5.7"
        assert issues[0]["issue_type"] == "needs-review"

    async def test_accessible_authentication_paste_blocking(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = [
            {"type": "paste_blocked", "selector": "input[type='password']#pwd", "html": "<input type='password' onpaste='return false;'>"}
        ]

        issues = await analyze_accessible_authentication(mock_page, "https://example.com")
        assert len(issues) == 1
        assert issues[0]["rule_id"] == "auth-paste-blocked"
        assert issues[0]["wcag_criterion"] == "3.3.8"
        assert issues[0]["severity"] == "serious"

    async def test_consistent_help_evaluation(self):
        # Case 1: inconsistent help order across pages
        pages_inconsistent = [
            {"url": "https://example.com/home", "help_mechanisms": ["chat", "contact", "faq"]},
            {"url": "https://example.com/pricing", "help_mechanisms": ["faq", "chat", "contact"]},
        ]
        issues = evaluate_consistent_help(pages_inconsistent, "https://example.com")
        assert len(issues) == 1
        assert issues[0]["rule_id"] == "consistent-help-inconsistent"
        assert issues[0]["wcag_criterion"] == "3.2.6"

        # Case 2: consistent help order
        pages_consistent = [
            {"url": "https://example.com/home", "help_mechanisms": ["chat", "contact"]},
            {"url": "https://example.com/pricing", "help_mechanisms": ["chat", "contact"]},
        ]
        issues_ok = evaluate_consistent_help(pages_consistent, "https://example.com")
        assert len(issues_ok) == 0

    async def test_redundant_entry_evaluation(self):
        form_inputs = [
            {"name": "shipping_street", "has_auto_populate": False, "html": "<input name='shipping_street'>"},
            {"name": "shipping_street", "has_auto_populate": False, "html": "<input name='shipping_street'>"},
        ]
        issues = evaluate_redundant_entry(form_inputs, "https://example.com")
        assert len(issues) == 1
        assert issues[0]["rule_id"] == "redundant-entry"
        assert issues[0]["wcag_criterion"] == "3.3.7"
