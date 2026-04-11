import copy

from app.services.prioritizer import build_scoring_summary, prioritize_issues


def _issue(
    rule_id: str,
    *,
    issue_type: str = "violation",
    wcag_level: str = "AA",
    element_type: str = "text",
    frequency: int = 1,
    user_impact=None,
    severity: str = "moderate",
    fix=None,
    confidence: float = 0.9,
    html_snippet: str = "",
    evidence: dict | None = None,
):
    return {
        "rule_id": rule_id,
        "issue_type": issue_type,
        "wcag_level": wcag_level,
        "element_type": element_type,
        "frequency": frequency,
        "user_impact": user_impact,
        "severity": severity,
        "fix": fix or {"description": f"Fix {rule_id}"},
        "message": f"{rule_id} issue",
        "domain": "forms" if element_type in {"input", "button", "form"} else "structure",
        "confidence": confidence,
        "html_snippet": html_snippet,
        "evidence": evidence or {},
    }


def test_identical_inputs_produce_identical_outputs():
    issues = [
        _issue("missing-label", element_type="input", frequency=3, user_impact="blocks action", severity="critical"),
        _issue("link-purpose", element_type="link", frequency=2, user_impact="confusing", severity="moderate"),
        _issue("missing-alt", element_type="image", frequency=1, user_impact="minor", severity="minor"),
    ]

    summary_one = build_scoring_summary(copy.deepcopy(issues))
    summary_two = build_scoring_summary(copy.deepcopy(issues))

    assert summary_one["overall_score"] == summary_two["overall_score"]
    assert summary_one["severity_breakdown"] == summary_two["severity_breakdown"]
    assert summary_one["prioritized_issues"] == summary_two["prioritized_issues"]
    assert summary_one["recommendations"] == summary_two["recommendations"]
    assert summary_one["priority_score_distribution"] == summary_two["priority_score_distribution"]


def test_adding_one_critical_issue_drops_score_clearly():
    baseline = build_scoring_summary([
        _issue("link-purpose", element_type="link", frequency=2, user_impact="confusing", severity="moderate"),
    ])
    with_critical = build_scoring_summary([
        _issue("link-purpose", element_type="link", frequency=2, user_impact="confusing", severity="moderate"),
        _issue("missing-label", element_type="input", frequency=1, user_impact="blocks action", severity="critical", wcag_level="A"),
    ])

    assert with_critical["overall_score"] < baseline["overall_score"]
    assert with_critical["overall_score"] <= 85.0
    assert with_critical["severity_breakdown"]["critical"] == 1
    assert with_critical["prioritized_issues"][0]["rule_id"] == "missing-label"


def test_removing_issues_improves_score_proportionally():
    heavy = build_scoring_summary([
        _issue("missing-label", element_type="input", frequency=4, user_impact="blocks action", severity="critical", wcag_level="A"),
        _issue("link-purpose", element_type="link", frequency=3, user_impact="confusing", severity="moderate"),
        _issue("missing-alt", element_type="image", frequency=2, user_impact="minor", severity="minor"),
    ])
    reduced = build_scoring_summary([
        _issue("link-purpose", element_type="link", frequency=3, user_impact="confusing", severity="moderate"),
        _issue("missing-alt", element_type="image", frequency=2, user_impact="minor", severity="minor"),
    ])

    assert reduced["overall_score"] > heavy["overall_score"]
    assert reduced["severity_breakdown"]["critical"] == 0
    assert heavy["score_distribution"]["critical_penalty"] > reduced["score_distribution"]["critical_penalty"]


def test_priority_order_is_deterministic_for_ties():
    issues = [
        _issue("rule-b", element_type="link", frequency=1, user_impact="minor", severity="minor"),
        _issue("rule-a", element_type="link", frequency=1, user_impact="minor", severity="minor"),
    ]

    prioritized, ranking = prioritize_issues(copy.deepcopy(issues))

    assert prioritized[0]["rule_id"] == "rule-a"
    assert prioritized[1]["rule_id"] == "rule-b"
    assert ranking[0]["rule_id"] == "rule-a"


def test_duplicate_pattern_grouping_is_stable():
    issues = [
        _issue("missing-alt", issue_type="violation", element_type="image", frequency=2, user_impact="minor", severity="minor"),
        _issue("missing-alt", issue_type="violation", element_type="image", frequency=3, user_impact="minor", severity="minor"),
        _issue("missing-alt", issue_type="violation", element_type="image", frequency=1, user_impact="minor", severity="minor"),
    ]

    summary = build_scoring_summary(copy.deepcopy(issues))
    by_pattern = summary["issue_groupings"]["by_pattern"]

    assert len(by_pattern) == 1
    assert by_pattern[0]["issue_count"] == 3
    assert by_pattern[0]["frequency"] == 6.0


def test_repeated_occurrences_have_diminishing_penalty():
    single = build_scoring_summary([
        _issue("link-purpose", element_type="link", frequency=1, user_impact="confusing", severity="moderate"),
    ])
    repeated = build_scoring_summary([
        _issue("link-purpose", element_type="link", frequency=10, user_impact="confusing", severity="moderate"),
    ])

    single_penalty = float(single["score_distribution"]["major_penalty"])
    repeated_penalty = float(repeated["score_distribution"]["major_penalty"])

    assert repeated_penalty > single_penalty
    # Sub-linear scaling should be materially below a linear x10 penalty jump.
    assert repeated_penalty < (single_penalty * 6.0)


def test_low_confidence_issues_are_excluded_from_score_and_summary():
    summary = build_scoring_summary(
        [
            _issue(
                "missing-label",
                element_type="input",
                frequency=1,
                user_impact="blocks action",
                severity="critical",
                confidence=0.2,
            ),
            _issue(
                "link-purpose",
                element_type="link",
                frequency=1,
                user_impact="confusing",
                severity="moderate",
                confidence=0.9,
            ),
        ]
    )

    assert summary["severity_breakdown"]["critical"] == 0
    assert all(issue["rule_id"] != "missing-label" for issue in summary["prioritized_issues"])
    assert summary["score_explanation"]["low_confidence_excluded_count"] >= 1


def test_hidden_elements_have_reduced_penalty_weight():
    visible = build_scoring_summary([
        _issue("svg-accessible-name", severity="serious", confidence=0.9, html_snippet="<svg></svg>"),
    ])
    hidden = build_scoring_summary([
        _issue(
            "svg-accessible-name",
            severity="serious",
            confidence=0.9,
            html_snippet='<svg aria-hidden="true"></svg>',
        ),
    ])

    assert hidden["overall_score"] >= visible["overall_score"]
    assert hidden["score_distribution"]["major_penalty"] < visible["score_distribution"]["major_penalty"]
