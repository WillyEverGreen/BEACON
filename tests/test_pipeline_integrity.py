"""
Test suite for BEACON Pipeline Integrity and Ordering Invariants.
Validates:
- Scanner says FAIL -> AI says PASS -> finding disappears -> score is calculated WITHOUT it
- Multi-signal confidence calibration uses real verification_result from adjudication
- Root-cause clustering consolidates 5 structural landmark rules into 1 primary finding before scoring
- Hybrid required rules run before precision profile filtering
"""
import pytest

from app.services.adjudicator import adjudicate_issues
from app.services.confidence import apply_confidence_rules
from app.services.grouper import cluster_root_causes
from app.services.prioritizer import build_scoring_summary


@pytest.mark.asyncio
async def test_false_positive_suppression_affects_score():
    """Verify that when AI adjudication marks an issue PASS, it is excluded from scoring."""
    # A page with a contextual link: <h2>Pricing</h2><p>Compare plans.</p><a href="/pricing">Learn more</a>
    # A scanner might flag generic-link-text, but AI adjudication marks it PASS.
    html = """
    <!DOCTYPE html>
    <html lang="en">
      <head><title>Pricing Page</title></head>
      <body>
        <main>
          <h2>Pricing Plans</h2>
          <p>Compare plans and pricing details.</p>
          <a id="lnk" href="/pricing">Learn more</a>
        </main>
      </body>
    </html>
    """
    raw_issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "severity": "moderate",
        "element": "a#lnk",
        "html_snippet": '<a id="lnk" href="/pricing">Learn more</a>',
        "confidence_sources": ["scanner"],
    }

    # Step 1: Adjudication
    verified_failures, verified_passes, needs_review = await adjudicate_issues(
        [raw_issue],
        html=html,
    )
    assert len(verified_passes) == 1
    assert len(verified_failures) == 0

    # Step 2: Scoring summary computed on remaining issues (0 issues)
    # The suppressed pass does NOT decrease the score!
    scoring = build_scoring_summary(verified_failures)
    assert len(scoring["prioritized_issues"]) == 0
    assert scoring["overall_score"] == 100.0


def test_confidence_calibration_uses_adjudication_verdict():
    """Verify that confidence calibration extracts verification_confidence from verification_result."""
    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "severity": "moderate",
        "element": "a#lnk",
        "html_snippet": '<a id="lnk" href="/pricing">Learn more</a>',
        "confidence_sources": ["scanner"],
        "verification_result": {
            "verdict": "fail",
            "confidence": 0.88,
            "wcag_applicable": True,
            "wcag_criterion": "2.4.4",
        }
    }

    calibrated = apply_confidence_rules([issue])
    assert calibrated[0]["verification_confidence"] == 0.88
    assert "confidence_breakdown" in calibrated[0]
    assert calibrated[0]["confidence_breakdown"]["verification_confidence"] == 0.88


def test_root_cause_clustering_reduces_scoring_penalty():
    """Verify that clustering 5 landmark findings into 1 primary finding reduces redundant penalty in score."""
    landmark_issues = [
        {"rule_id": "region", "element": "body", "wcag_criterion": "1.3.1", "severity": "moderate", "confidence": 0.9, "confidence_tier": "high", "confidence_sources": ["axe-core"]},
        {"rule_id": "aria_content_in_landmark", "element": "body", "wcag_criterion": "1.3.1", "severity": "moderate", "confidence": 0.9, "confidence_tier": "high", "confidence_sources": ["axe-core"]},
        {"rule_id": "no-main-landmark", "element": "body", "wcag_criterion": "1.3.1", "severity": "moderate", "confidence": 0.9, "confidence_tier": "high", "confidence_sources": ["static"]},
        {"rule_id": "landmark-roles", "element": "body", "wcag_criterion": "1.3.1", "severity": "moderate", "confidence": 0.9, "confidence_tier": "high", "confidence_sources": ["axe-core"]},
        {"rule_id": "landmark-one-main", "element": "body", "wcag_criterion": "1.3.1", "severity": "moderate", "confidence": 0.9, "confidence_tier": "high", "confidence_sources": ["axe-core"]},
    ]

    # Without clustering, 5 violations penalized
    unclustered_summary = build_scoring_summary(landmark_issues)
    assert len(unclustered_summary["prioritized_issues"]) == 5

    # With root-cause clustering, only 1 primary finding is passed to scoring
    clustered, secondary = cluster_root_causes(landmark_issues)
    assert len(clustered) == 1
    assert len(secondary) == 4

    clustered_summary = build_scoring_summary(clustered)
    assert len(clustered_summary["prioritized_issues"]) == 1
    # Clustered score is significantly higher (less penalized) than unclustered
    assert clustered_summary["overall_score"] > unclustered_summary["overall_score"]
