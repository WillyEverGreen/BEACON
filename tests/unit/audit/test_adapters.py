"""Unit tests for Phase 3 Audit Engine Adapters."""

import pytest
from app.audit.adapters.axe_adapter import AxeAdapter
from app.audit.adapters.heuristics_adapter import HeuristicsAdapter


def test_axe_adapter_normalization():
    adapter = AxeAdapter(engine_version="4.10.2", rule_version="4.10.2")

    raw_violation = {
        "id": "color-contrast",
        "impact": "serious",
        "tags": ["cat.color", "wcag2aa", "wcag143", "ACT-afw4f7"],
        "description": "Ensures the contrast between foreground and background colors meets WCAG 2 AA minimum thresholds",
        "help": "Elements must meet minimum color contrast ratio thresholds",
        "helpUrl": "https://dequeuniversity.com/rules/axe/4.10/color-contrast",
        "nodes": [
            {
                "any": [{"id": "color-contrast", "data": {"fgColor": "#777777", "bgColor": "#ffffff", "contrastRatio": 4.48}}],
                "all": [],
                "none": [],
                "impact": "serious",
                "html": "<span class=\"text-muted\">Subtle subtitle text</span>",
                "target": ["span.text-muted"],
                "failureSummary": "Fix any of the following:\n  Element has insufficient color contrast of 4.48 (foreground color: #777777, background color: #ffffff, font size: 12.0pt (16px), font weight: normal). Expected contrast ratio of 4.5:1",
            }
        ],
    }

    finding = adapter.normalize(raw_violation)
    assert finding.rule_id == "color-contrast"
    assert finding.engine == "axe"
    assert finding.engine_version == "4.10.2"
    assert finding.wcag_criterion == "1.4.3"
    assert finding.wcag_level == "AA"
    assert finding.severity == "serious"
    assert finding.selector == "span.text-muted"
    assert "4.48" in finding.message
    assert finding.act_rule_id == "ACT-afw4f7"
    assert finding.evidence["axe_help_url"] == "https://dequeuniversity.com/rules/axe/4.10/color-contrast"


def test_heuristics_adapter_normalization():
    adapter = HeuristicsAdapter(rule_version="2.1.0")

    raw_heuristic = {
        "rule_id": "beacon-heading-order",
        "severity": "moderate",
        "wcag_criterion": "1.3.1",
        "wcag_level": "A",
        "selector": "main > h3.subtitle",
        "element_html": "<h3 class='subtitle'>Jumped from H1</h3>",
        "description": "Heading level skipped from h1 to h3",
        "confidence": 0.85,
        "details": {"previous_level": 1, "current_level": 3},
    }

    finding = adapter.normalize(raw_heuristic)
    assert finding.rule_id == "beacon-heading-order"
    assert finding.engine == "beacon_heuristics"
    assert finding.wcag_criterion == "1.3.1"
    assert finding.confidence == 0.85
    assert finding.severity == "moderate"
    assert finding.selector == "main > h3.subtitle"
