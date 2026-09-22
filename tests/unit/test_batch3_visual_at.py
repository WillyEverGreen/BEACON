"""
Unit tests for Batch 3: Visual & AT (§17–§21).
Verifies:
- §17: capture_visual_evidence
- §18: calculate_apca_contrast and analyze_rendered_contrast
- §19: analyze_color_only_information
- §20 & §21: AssistiveTechManager and AT evidence model
"""

from unittest.mock import AsyncMock

import pytest

from app.services.visual_accessibility import (
    AssistiveTechManager,
    analyze_color_only_information,
    analyze_rendered_contrast,
    calculate_apca_contrast,
    capture_visual_evidence,
)


@pytest.mark.asyncio
class TestBatch3VisualAndAT:

    async def test_capture_visual_evidence(self):
        mock_page = AsyncMock()
        mock_page.evaluate.side_effect = [
            # Element geometry
            {
                "rect": {"x": 10, "y": 20, "width": 200, "height": 50},
                "computed": {"color": "rgb(0, 0, 0)", "backgroundColor": "rgb(255, 255, 255)", "fontSize": "16px"}
            },
            # Viewport info
            {
                "width": 1920, "height": 1080, "devicePixelRatio": 1.0, "scrollX": 0, "scrollY": 0
            }
        ]

        res = await capture_visual_evidence(mock_page, selector="h1.main")
        assert res["captured"] is True
        assert res["viewport"]["width"] == 1920
        assert res["element_geometry"]["rect"]["width"] == 200

    async def test_calculate_apca_contrast(self):
        # Black on white (positive Lc in APCA)
        black = (0, 0, 0)
        white = (255, 255, 255)
        apca_dark_on_light = calculate_apca_contrast(black, white)
        assert apca_dark_on_light > 100.0  # ~106 Lc

        # White on black (negative Lc in APCA indicating light-on-dark polarity)
        apca_light_on_dark = calculate_apca_contrast(white, black)
        assert abs(apca_light_on_dark) > 100.0
        assert apca_light_on_dark < -100.0

        # Gray on white (low contrast)
        gray = (200, 200, 200)
        apca_low = calculate_apca_contrast(gray, white)
        assert abs(apca_low) < 40.0

    async def test_analyze_rendered_contrast_violation(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = [
            {
                "selector": "p.caption",
                "text": "Subtle caption text",
                "html": "<p class='caption'>Subtle caption text</p>",
                "fg_rgb": [150, 150, 150],
                "bg_rgb": [255, 255, 255],
                "bg_type": "solid",
                "is_large_text": False,
                "font_size": 14,
            }
        ]

        issues = await analyze_rendered_contrast(mock_page, "https://example.com")
        assert len(issues) == 1
        issue = issues[0]
        assert issue["rule_id"] == "rendered-color-contrast"
        assert issue["wcag_criterion"] == "1.4.3"
        assert issue["wcag_level"] == "AA"
        assert "evidence" in issue
        assert "apca_contrast_advisory" in issue["evidence"]
        assert issue["evidence"]["contrast_ratio"] < 4.5

    async def test_analyze_color_only_information(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = [
            {"type": "link_color_only", "selector": "a#more-info", "html": "<a id='more-info'>Read more</a>", "text": "Read more"},
            {"type": "status_color_only", "selector": "span.dot-indicator", "html": "<span class='dot-indicator'></span>"},
        ]

        issues = await analyze_color_only_information(mock_page, "https://example.com")
        assert len(issues) == 2

        # Link in text color-only violation
        link_issue = [i for i in issues if i["rule_id"] == "link-in-text-color-only"][0]
        assert link_issue["wcag_criterion"] == "1.4.1"
        assert link_issue["issue_type"] == "violation"

        # Status indicator color-only needs review
        status_issue = [i for i in issues if i["rule_id"] == "status-indicator-color-only"][0]
        assert status_issue["wcag_criterion"] == "1.4.1"
        assert status_issue["issue_type"] == "needs-review"

    async def test_assistive_tech_manager_evidence_model_untested(self):
        mgr = AssistiveTechManager()
        model = mgr.create_at_evidence_model(tested=False)
        assert "assistive_technology" in model
        at = model["assistive_technology"]
        assert at["tested"] is False
        assert "reason" in at
        assert "unavailable" in at["reason"].lower()

    async def test_assistive_tech_manager_evidence_model_tested(self):
        mgr = AssistiveTechManager()
        speech = [
            {"event": "focus", "role": "button", "name": "Submit", "state": "enabled"}
        ]
        obs = ["Button announced correctly with accessible name 'Submit'"]
        model = mgr.create_at_evidence_model(
            provider="Guidepup_Virtual_SR",
            tested=True,
            speech_events=speech,
            observations=obs
        )
        assert "assistive_technology" in model
        at = model["assistive_technology"]
        assert at["tested"] is True
        assert at["provider"] == "Guidepup_Virtual_SR"
        assert len(at["speech_events"]) == 1
        assert at["speech_events"][0]["name"] == "Submit"
