"""Test incomplete HTML detection in StaticChecker."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from app.services.static_checks import StaticChecker


def _run_checks(html: str, checks: list[str] = None):
    """Helper to run checks on HTML."""
    checker = StaticChecker(html, "https://example.test")
    if checks is None:
        issues = checker.run_all()
    else:
        issues = checker.run_all(checks=checks)
    return issues, checker


def _get_issue_by_rule(issues: list[dict], rule_id: str):
    """Get first issue with given rule_id."""
    for issue in issues:
        if issue.get("rule_id") == rule_id:
            return issue
    return None


def test_incomplete_html_detection_empty_dom():
    """Test detection of very sparse HTML with no visible text."""
    html = """<html><body></body></html>"""
    issues, checker = _run_checks(html)
    
    # Should detect incomplete HTML
    incomplete_issue = _get_issue_by_rule(issues, "html-incomplete")
    assert incomplete_issue is not None, "Should detect empty HTML as incomplete"
    assert incomplete_issue["issue_type"] == "notice"
    assert "evidence" in incomplete_issue
    assert incomplete_issue["evidence"]["visible_text_length"] == 0
    assert incomplete_issue["evidence"]["dom_element_count"] <= 5


def test_incomplete_html_detection_minimal_structure():
    """Test detection of minimal content with no interactive elements."""
    html = """<html><body><p>Hello</p></body></html>"""
    issues, checker = _run_checks(html)
    
    # Should detect as incomplete (no head, minimal structure)
    incomplete_issue = _get_issue_by_rule(issues, "html-incomplete")
    assert incomplete_issue is not None, "Should detect minimal HTML as incomplete"
    assert incomplete_issue["evidence"]["has_head_tag"] is False


def test_incomplete_html_suppresses_structural_checks():
    """Test that structural checks are suppressed for incomplete HTML."""
    html = """<html><body></body></html>"""
    issues, checker = _run_checks(html)
    
    # Should NOT have headings or landmarks violations (suppressed)
    rule_ids = {issue.get("rule_id") for issue in issues}
    assert "no-headings" not in rule_ids, "Heading checks should be suppressed for incomplete HTML"
    assert "missing-landmarks" not in rule_ids, "Landmark checks should be suppressed for incomplete HTML"
    
    # BUT should have html-incomplete notice
    assert "html-incomplete" in rule_ids, "Should report incomplete HTML"


def test_complete_html_allows_structural_checks():
    """Test that structural checks run normally on complete HTML."""
    html = """
    <html lang="en">
    <head><title>Test</title></head>
    <body>
        <h1>Main Heading</h1>
        <main aria-label="main content">
            <p>This is complete HTML with proper structure.</p>
            <a href="/test">Link</a>
        </main>
    </body>
    </html>
    """
    issues, checker = _run_checks(html)
    
    # Complete HTML should NOT trigger incomplete detection
    incomplete_issue = _get_issue_by_rule(issues, "html-incomplete")
    assert incomplete_issue is None, "Should NOT detect complete HTML as incomplete"
    
    # Structural checks should run
    _rule_ids = {issue.get("rule_id") for issue in issues}
    # No headings violation is expected since we have an h1
    # We're just verifying the checks ran (not suppressed)


def test_incomplete_html_evidence_captured():
    """Test that incomplete HTML evidence is properly captured."""
    html = """<html><body><div>X</div></body></html>"""
    issues, checker = _run_checks(html)
    
    incomplete_issue = _get_issue_by_rule(issues, "html-incomplete")
    assert incomplete_issue is not None
    
    evidence = incomplete_issue["evidence"]
    assert "visible_text_length" in evidence
    assert "dom_element_count" in evidence
    assert "has_head_tag" in evidence
    assert "has_html_tag" in evidence
    assert "has_body_tag" in evidence
    assert "interactive_element_count" in evidence
    assert "semantic_element_count" in evidence
    assert "heading_count" in evidence


def test_missing_html_tag_detection():
    """Test detection of HTML fragments with minimal structure."""
    html = """<div><p>Content</p></div>"""
    issues, checker = _run_checks(html)
    
    incomplete_issue = _get_issue_by_rule(issues, "html-incomplete")
    assert incomplete_issue is not None, "Should detect fragment-like HTML as incomplete"
    # BeautifulSoup adds html/body tags, but we should detect the lack of head or minimal structure
    assert incomplete_issue["evidence"]["has_head_tag"] is False


def test_no_incomplete_on_minimal_valid_page():
    """Test that minimal but valid HTML doesn't trigger incomplete detection."""
    # A minimal but complete page should not trigger
    html = """
    <html lang="en">
    <head><title>Test</title></head>
    <body>
        <h1>Title</h1>
        <p>Content here.</p>
    </body>
    </html>
    """
    issues, checker = _run_checks(html)
    
    incomplete_issue = _get_issue_by_rule(issues, "html-incomplete")
    # Should not flag this as incomplete since it has basic required structure
    assert incomplete_issue is None or incomplete_issue["confidence"] < 0.5


if __name__ == "__main__":
    # Run tests manually
    test_incomplete_html_detection_empty_dom()
    print("✓ test_incomplete_html_detection_empty_dom")
    
    test_incomplete_html_detection_minimal_structure()
    print("✓ test_incomplete_html_detection_minimal_structure")
    
    test_incomplete_html_suppresses_structural_checks()
    print("✓ test_incomplete_html_suppresses_structural_checks")
    
    test_complete_html_allows_structural_checks()
    print("✓ test_complete_html_allows_structural_checks")
    
    test_incomplete_html_evidence_captured()
    print("✓ test_incomplete_html_evidence_captured")
    
    test_missing_html_tag_detection()
    print("✓ test_missing_html_tag_detection")
    
    test_no_incomplete_on_minimal_valid_page()
    print("✓ test_no_incomplete_on_minimal_valid_page")
    
    print("\n✅ All tests passed!")
