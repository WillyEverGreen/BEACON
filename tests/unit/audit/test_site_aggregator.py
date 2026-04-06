import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from app.audit.models import PageAuditResult
from app.audit.site_aggregator import aggregate_site_results


def _page(url: str, score: float, issues: list[dict], dom: str = "") -> PageAuditResult:
    return PageAuditResult(
        url=url,
        score=score,
        issues=issues,
        engine_timings={},
        page_dom=dom,
    )


def _issue(rule_id: str, selector: str, severity: str = "moderate", confidence: float = 0.8) -> dict:
    return {
        "rule_id": rule_id,
        "wcag_criterion": "1.3.1",
        "element_selector_fingerprint": selector,
        "severity": severity,
        "confidence": confidence,
    }


def test_deduplicates_same_rule_across_pages():
    pages = [
        _page("https://example.com/a", 80, [_issue("missing-alt", "img.hero")]),
        _page("https://example.com/b", 70, [_issue("missing-alt", "img.hero")]),
    ]

    result = aggregate_site_results(pages, "deep")

    assert len(result.issues) == 1


def test_affected_pages_count_correct():
    pages = [
        _page("https://example.com/a", 80, [_issue("missing-alt", "img.hero")]),
        _page("https://example.com/b", 70, [_issue("missing-alt", "img.hero")]),
        _page("https://example.com/c", 90, [_issue("color-contrast", "button.cta")]),
    ]

    result = aggregate_site_results(pages, "deep")
    issue = next(item for item in result.issues if item["rule_id"] == "missing-alt")

    assert issue["affected_pages"] == 2


def test_site_score_weighted_by_page_priority():
    pages = [
        _page("https://example.com/login", 40, [_issue("missing-label", "input.email")]),
        _page("https://example.com/blog/post-1", 100, [_issue("none", "x")], dom="<article>post</article>"),
    ]

    result = aggregate_site_results(pages, "deep")

    assert result.site_score == 60.0


def test_worst_page_score_is_minimum():
    pages = [
        _page("https://example.com/a", 88, []),
        _page("https://example.com/b", 42, []),
        _page("https://example.com/c", 70, []),
    ]

    result = aggregate_site_results(pages, "deep")

    assert result.worst_page_score == 42.0
    assert result.worst_page["url"] == "https://example.com/b"


def test_priority_ranking_cross_page_frequency():
    pages = [
        _page("https://example.com/p1", 70, [_issue("rule-a", "x", severity="serious", confidence=1.0)]),
        _page("https://example.com/p2", 68, [_issue("rule-a", "x", severity="serious", confidence=1.0)]),
        _page(
            "https://example.com/p3",
            66,
            [
                _issue("rule-a", "x", severity="serious", confidence=1.0),
                _issue("rule-b", "y", severity="critical", confidence=1.0),
            ],
        ),
    ]

    result = aggregate_site_results(pages, "deep")

    assert result.priority_ranking[0]["rule_id"] == "rule-a"
    assert result.priority_ranking[0]["affected_pages"] == 3


def test_executive_summary_fields_complete():
    pages = [
        _page("https://example.com/a", 80, [_issue("missing-alt", "img.hero", severity="critical")]),
        _page("https://example.com/b", 90, []),
    ]

    result = aggregate_site_results(pages, "deep")
    summary = result.executive_summary

    for key in (
        "site_score",
        "worst_page",
        "best_page",
        "critical_issues",
        "pages_audited",
        "pages_discovered",
        "top_fix",
    ):
        assert key in summary


def test_fix_once_fixes_all_flag_set_correctly():
    pages = [
        _page("https://example.com/a", 60, [_issue("shared-rule", "#global")]),
        _page("https://example.com/b", 55, [_issue("shared-rule", "#global")]),
        _page("https://example.com/c", 50, [_issue("shared-rule", "#global")]),
    ]

    result = aggregate_site_results(pages, "deep")
    shared = next(item for item in result.priority_ranking if item["rule_id"] == "shared-rule")

    assert shared["fix_once_fixes_all"] is True


def test_cross_page_dedup_ignores_dynamic_selector_parts():
    pages = [
        _page(
            "https://example.com/a",
            70,
            [
                {
                    "rule_id": "focus-order",
                    "wcag_criterion": "2.4.3",
                    "element_selector_fingerprint": "div.card.css-a1b2c3:nth-child(2) > a.cta",
                    "severity": "serious",
                    "confidence": 0.9,
                }
            ],
        ),
        _page(
            "https://example.com/b",
            72,
            [
                {
                    "rule_id": "focus-order",
                    "wcag_criterion": "2.4.3",
                    "element_selector_fingerprint": "div.card.css-z9y8x7:nth-child(6) > a.cta",
                    "severity": "serious",
                    "confidence": 0.85,
                }
            ],
        ),
    ]

    result = aggregate_site_results(pages, "deep")

    assert len(result.issues) == 1
    assert result.issues[0]["affected_pages"] == 2


def test_non_empty_pages_never_emit_zero_site_score():
    pages = [
        _page("https://example.com/a", 0.0, []),
        _page("https://example.com/b", 0.0, []),
    ]

    result = aggregate_site_results(pages, "deep")

    assert result.pages_audited == 2
    assert result.site_score > 0.0
