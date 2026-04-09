from app.crawlers.site_aggregator import aggregate_site_issues


def test_cross_page_dedup_merges_matching_issues():
    page_results = [
        {
            "url": "https://example.com/a",
            "issues": [
                {
                    "issue_type": "missing-label",
                    "rule_id": "missing-label",
                    "wcag_criterion": "3.3.2",
                    "severity": "serious",
                    "selector": "#btn-12345 > span",
                    "element_role": "button",
                    "frequency": 2,
                    "confidence": 0.8,
                    "suggested_fix": "Add explicit label",
                }
            ],
        },
        {
            "url": "https://example.com/b",
            "issues": [
                {
                    "issue_type": "missing-label",
                    "rule_id": "missing-label",
                    "wcag_criterion": "3.3.2",
                    "severity": "critical",
                    "selector": "#btn-67890 > span",
                    "element_role": "button",
                    "frequency": 3,
                    "confidence": 0.9,
                    "suggested_fix": "Add explicit label",
                }
            ],
        },
    ]

    result = aggregate_site_issues(page_results)
    aggregated = result["aggregated_issues"]

    assert len(aggregated) == 1
    merged = aggregated[0]
    assert merged["issue_type"] == "missing-label"
    assert merged["severity"] == "critical"
    assert merged["total_frequency"] == 5
    assert merged["affected_page_count"] == 2


def test_single_page_issues_are_retained():
    page_results = [
        {
            "url": "https://example.com/a",
            "issues": [
                {
                    "issue_type": "missing-label",
                    "rule_id": "missing-label",
                    "wcag_criterion": "3.3.2",
                    "severity": "critical",
                    "selector": "#btn-12345 > span",
                    "element_role": "button",
                    "frequency": 2,
                    "confidence": 0.9,
                }
            ],
        },
        {
            "url": "https://example.com/c",
            "issues": [
                {
                    "issue_type": "missing-alt",
                    "rule_id": "missing-alt",
                    "wcag_criterion": "1.1.1",
                    "severity": "minor",
                    "selector": ".hero img",
                    "element_role": "image",
                    "frequency": 1,
                    "confidence": 0.7,
                }
            ],
        },
    ]

    result = aggregate_site_issues(page_results)
    aggregated = result["aggregated_issues"]

    assert len(aggregated) == 2
    unique = next(item for item in aggregated if item["issue_type"] == "missing-alt")
    assert unique["affected_page_count"] == 1
    assert unique["total_frequency"] == 1


def test_priority_recomputation_uses_site_wide_frequency_weighting():
    page_results = [
        {
            "url": "https://example.com/a",
            "issues": [
                {
                    "issue_type": "missing-label",
                    "rule_id": "missing-label",
                    "wcag_criterion": "3.3.2",
                    "severity": "critical",
                    "selector": "#btn-111 > span",
                    "element_role": "button",
                    "frequency": 4,
                    "confidence": 0.9,
                },
                {
                    "issue_type": "missing-alt",
                    "rule_id": "missing-alt",
                    "wcag_criterion": "1.1.1",
                    "severity": "minor",
                    "selector": ".hero img",
                    "element_role": "image",
                    "frequency": 1,
                    "confidence": 0.7,
                },
            ],
        },
        {
            "url": "https://example.com/b",
            "issues": [
                {
                    "issue_type": "missing-label",
                    "rule_id": "missing-label",
                    "wcag_criterion": "3.3.2",
                    "severity": "critical",
                    "selector": "#btn-222 > span",
                    "element_role": "button",
                    "frequency": 3,
                    "confidence": 0.9,
                }
            ],
        },
    ]

    result = aggregate_site_issues(page_results)
    top = result["top_priorities"][0]

    assert top["issue_type"] == "missing-label"
    assert top["aggregated_priority_score"] > 0
