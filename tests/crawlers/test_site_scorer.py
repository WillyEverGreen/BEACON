from app.crawlers.site_scorer import compute_site_score


def test_weighted_average_score_is_computed_for_successful_pages():
    page_results = [
        {"audit_status": "success", "score": 80.0, "page_weight": 1.0},
        {"audit_status": "success", "score": 100.0, "page_weight": 0.8},
    ]
    aggregated_issues = []

    site_score = compute_site_score(page_results, aggregated_issues)

    assert site_score == 88.9


def test_critical_penalty_is_capped_at_20_points():
    page_results = [
        {"audit_status": "success", "score": 95.0, "page_weight": 1.0},
    ]
    aggregated_issues = [{"severity": "critical"} for _ in range(20)]

    site_score = compute_site_score(page_results, aggregated_issues)

    assert site_score == 75.0


def test_failed_pages_are_excluded_from_score():
    page_results = [
        {"audit_status": "success", "score": 92.0, "page_weight": 1.0},
        {"audit_status": "timeout", "score": 10.0, "page_weight": 1.0},
        {"audit_status": "error", "score": 10.0, "page_weight": 1.0},
    ]

    site_score = compute_site_score(page_results, aggregated_issues=[])

    assert site_score == 92.0


def test_zero_successful_pages_returns_null_score():
    page_results = [
        {"audit_status": "timeout", "score": None, "page_weight": 1.0},
        {"audit_status": "error", "score": None, "page_weight": 1.0},
    ]

    site_score = compute_site_score(page_results, aggregated_issues=[])

    assert site_score is None
