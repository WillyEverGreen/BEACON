from app.routers.audit import _build_explain_payload
from app.services.audit_runner import _enforce_audit_invariants
from app.services.prioritizer import build_scoring_summary


def _issue(rule_id: str, *, confidence: float, severity: str = "moderate", frequency: int = 1, html_snippet: str = "") -> dict:
    return {
        "rule_id": rule_id,
        "issue_type": "violation",
        "wcag_level": "AA",
        "element_type": "text",
        "frequency": frequency,
        "user_impact": "confusing",
        "severity": severity,
        "confidence": confidence,
        "message": f"{rule_id} issue",
        "html_snippet": html_snippet,
    }


def test_low_confidence_findings_not_in_summary_or_score():
    summary = build_scoring_summary(
        [
            _issue("missing-label", confidence=0.2, severity="critical"),
            _issue("link-purpose", confidence=0.91, severity="moderate"),
        ]
    )

    assert summary["severity_breakdown"]["critical"] == 0
    assert all(issue["rule_id"] != "missing-label" for issue in summary["prioritized_issues"])
    assert summary["score_explanation"]["low_confidence_excluded_count"] >= 1


def test_occurrence_count_present_without_list_inflation():
    summary = build_scoring_summary(
        [
            _issue("link-purpose", confidence=0.91, frequency=5),
            _issue("heading-order", confidence=0.91, frequency=3),
        ]
    )

    assert len(summary["prioritized_issues"]) == 2
    first = summary["prioritized_issues"][0]
    assert "occurrence_count" in first
    assert first["occurrence_count"] >= 1


def test_explain_payload_has_breakdown_and_confidence_summary():
    payload = _build_explain_payload(
        {
            "score_distribution": {
                "critical_penalty": 8.0,
                "major_penalty": 5.0,
                "minor_penalty": 2.0,
            },
            "score_explanation": {"quality_bonus": 1.0},
            "issues": [
                {"confidence_tier": "high", "confidence": 0.92},
                {"confidence_tier": "medium", "confidence": 0.73},
                {"confidence_tier": "low", "confidence": 0.34},
            ],
            "priority_ranking": [
                {"rule_id": "missing-label", "severity": "critical", "affected_count": 3}
            ],
        }
    )

    assert set(payload.keys()) == {"score_breakdown", "top_impact_issues", "confidence_summary"}
    assert payload["score_breakdown"]["critical_penalty"] == 8.0
    assert payload["score_breakdown"]["quality_bonus"] == 1.0
    assert payload["confidence_summary"] == {"high": 1, "medium": 1, "low": 1}
    assert payload["top_impact_issues"][0]["rule"] == "missing-label"


def test_pages_scanned_alias_is_always_emitted():
    normalized = _enforce_audit_invariants(
        {
            "url": "https://example.com",
            "issues": [],
            "pages_audited": 3,
            "score": 95.0,
            "enrichment_status": "complete",
            "site_result": {"pages_audited": 3, "site_score": 95.0},
        }
    )

    assert normalized["pages_scanned"] == 3
    assert normalized["site_result"]["pages_scanned"] == 3
