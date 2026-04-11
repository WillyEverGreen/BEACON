from app.services.prioritizer import build_scoring_summary


def _issue(
    rule_id: str,
    *,
    severity: str = "moderate",
    confidence: float = 0.9,
    frequency: int = 1,
    wcag_level: str = "AA",
    element_type: str = "text",
    user_impact: str = "confusing",
) -> dict:
    return {
        "rule_id": rule_id,
        "issue_type": "violation",
        "wcag_level": wcag_level,
        "element_type": element_type,
        "frequency": frequency,
        "user_impact": user_impact,
        "severity": severity,
        "confidence": confidence,
        "message": f"{rule_id} issue",
    }


def test_site_archetype_score_ordering_and_ranges():
    gold = build_scoring_summary(
        [
            _issue("link-purpose", severity="moderate", frequency=2),
            _issue("heading-order", severity="moderate", frequency=1),
            _issue("svg-accessible-name", severity="minor", frequency=1, user_impact="minor"),
        ]
    )
    high_quality = build_scoring_summary(
        [
            _issue("link-purpose", severity="moderate", frequency=3),
            _issue("heading-order", severity="moderate", frequency=2),
            _issue("empty-alt", severity="minor", frequency=2, user_impact="minor"),
            _issue("no-aria-live", severity="minor", frequency=1, user_impact="minor"),
        ]
    )
    complex_real_world = build_scoring_summary(
        [
            _issue("missing-label", severity="critical", wcag_level="A", element_type="input", user_impact="blocks action"),
            _issue("link-purpose", severity="moderate", frequency=4),
            _issue("aria-required-parent", severity="serious", wcag_level="A", element_type="button", user_impact="confusing"),
            _issue("heading-order", severity="moderate", frequency=2),
            _issue("empty-alt", severity="minor", frequency=2, user_impact="minor"),
        ]
    )
    legacy_poor = build_scoring_summary(
        [
            _issue("missing-label", severity="critical", wcag_level="A", element_type="input", user_impact="blocks action", frequency=5),
            _issue("aria-required-parent", severity="critical", wcag_level="A", element_type="button", user_impact="blocks action", frequency=4),
            _issue("aria-required-children", severity="critical", wcag_level="A", element_type="button", user_impact="blocks action", frequency=4),
            _issue("button-name", severity="critical", wcag_level="A", element_type="button", user_impact="blocks action", frequency=3),
            _issue("link-purpose", severity="moderate", frequency=6),
            _issue("heading-order", severity="moderate", frequency=5),
            _issue("empty-alt", severity="minor", frequency=8, user_impact="minor"),
        ]
    )

    assert gold["overall_score"] >= high_quality["overall_score"] >= complex_real_world["overall_score"] >= legacy_poor["overall_score"]

    assert 88.0 <= gold["overall_score"] <= 100.0
    assert 80.0 <= high_quality["overall_score"] <= 96.0
    assert 55.0 <= complex_real_world["overall_score"] <= 90.0
    assert 0.0 <= legacy_poor["overall_score"] <= 70.0


def test_score_variance_is_deterministic_within_two_points():
    issues = [
        _issue("missing-label", severity="critical", wcag_level="A", element_type="input", user_impact="blocks action", frequency=2),
        _issue("link-purpose", severity="moderate", frequency=4),
        _issue("heading-order", severity="moderate", frequency=3),
        _issue("svg-accessible-name", severity="minor", frequency=2, user_impact="minor"),
    ]

    s1 = build_scoring_summary([dict(i) for i in issues])["overall_score"]
    s2 = build_scoring_summary([dict(i) for i in issues])["overall_score"]
    s3 = build_scoring_summary([dict(i) for i in issues])["overall_score"]

    spread = max(s1, s2, s3) - min(s1, s2, s3)
    assert spread <= 2.0


def test_structural_fp_suppression_improves_score_ordering():
    """With structural FP rules removed, gold-standard sites score higher."""
    # Simulate a gold-standard site that triggers structural FPs
    gold_with_structural = build_scoring_summary(
        [
            _issue("landmark-roles", severity="moderate", frequency=3),
            _issue("region", severity="moderate", frequency=4),
            _issue("link-purpose", severity="moderate", frequency=1),
        ]
    )
    # Same site but structural FPs already filtered
    gold_without_structural = build_scoring_summary(
        [
            _issue("link-purpose", severity="moderate", frequency=1),
        ]
    )

    # Without structural noise, the score should be higher
    assert gold_without_structural["overall_score"] >= gold_with_structural["overall_score"]
    # The difference should be meaningful (>2 points)
    assert gold_without_structural["overall_score"] - gold_with_structural["overall_score"] >= 2.0


def test_quality_bonus_floors_high_quality_sites():
    """apply_quality_bonus floors scores for high-quality sites."""
    from app.services.confidence import apply_quality_bonus

    # Site with 2+ quality indicators → score floored at 75
    low_score = apply_quality_bonus(60.0, {
        "semantic_html_density": 0.90,
        "has_skip_link": True,
        "has_lang_attr": True,
    })
    assert low_score >= 75.0

    # Site with 0 quality indicators → score unchanged
    no_bonus = apply_quality_bonus(60.0, {
        "semantic_html_density": 0.3,
        "has_skip_link": False,
        "has_lang_attr": False,
    })
    assert no_bonus == 60.0

    # All 3 indicators → +3 bonus (capped at 100)
    high_score = apply_quality_bonus(95.0, {
        "semantic_html_density": 0.90,
        "has_skip_link": True,
        "has_lang_attr": True,
    })
    assert high_score >= 95.0
    assert high_score <= 100.0

    # GUARD: Critical violations present → no bonus applied
    critical_present = apply_quality_bonus(60.0, {
        "semantic_html_density": 0.90,
        "has_skip_link": True,
        "has_lang_attr": True,
        "has_critical_violations": True,
    })
    assert critical_present == 60.0  # unchanged — critical guard blocked bonus


def test_confidence_unchanged_by_visibility_policy():
    """DECOUPLING GUARD: Confidence values must not change based on visibility filtering.

    This test ensures the design constraint (confidence ≠ visibility) is maintained.
    _apply_precision_profile may DROP issues but must never MODIFY their confidence values.
    """
    from app.services.audit_runner import _apply_precision_profile

    issues = [
        {
            "rule_id": "landmark-roles",
            "issue_type": "violation",
            "wcag_level": "AA",
            "element_type": "text",
            "frequency": 1,
            "user_impact": "confusing",
            "severity": "moderate",
            "confidence": 0.85,
            "message": "test",
            "html_snippet": "",
            "rule_type": "hard",
            "needs_manual_review": False,
            "confidence_sources": ["static"],
        },
        {
            "rule_id": "missing-label",
            "issue_type": "violation",
            "wcag_level": "A",
            "element_type": "input",
            "frequency": 1,
            "user_impact": "blocks action",
            "severity": "critical",
            "confidence": 0.95,
            "message": "test",
            "html_snippet": "",
            "rule_type": "hard",
            "needs_manual_review": False,
            "confidence_sources": ["static"],
        },
    ]

    # Store original confidence values
    original_confidences = {i["rule_id"]: i["confidence"] for i in issues}

    kept, _ = _apply_precision_profile(issues, "production")

    # Verify kept issues have UNCHANGED confidence
    for issue in kept:
        rule_id = issue["rule_id"]
        assert issue["confidence"] == original_confidences[rule_id], (
            f"Confidence for {rule_id} was modified by visibility filter: "
            f"{original_confidences[rule_id]} → {issue['confidence']}"
        )

