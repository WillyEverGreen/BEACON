"""
Unit tests for evidence-driven landmark clustering, WCAG relationship classification,
and decoupled DOM extraction.
"""
import pytest
from app.services.static_checks import StaticChecker
from app.services.normalizer import normalize_all
from app.config import get_wcag_relationship


def test_nav_cluster_detection_targets_div_nav():
    """Unwrapped nav cluster (<div class="nav"><a>...</a></div>) targets the container, not body."""
    html = """<!DOCTYPE html>
    <html lang="en">
    <head><title>Portfolio</title></head>
    <body>
      <div class="nav">
        <a href="#about">About</a>
        <a href="#work">Work</a>
        <a href="#contact">Contact</a>
      </div>
      <main>
        <h1>Sai's Portfolio</h1>
        <p>Developer and designer.</p>
      </main>
      <footer>
        <p>&copy; 2026 Sai</p>
      </footer>
    </body>
    </html>"""
    checker = StaticChecker(html, "https://example.com")
    issues = checker.check_landmarks()
    
    nav_issues = [i for i in issues if i["rule_id"] == "no-nav-landmark"]
    assert len(nav_issues) == 1, "Expected exactly one no-nav-landmark issue"
    
    issue = nav_issues[0]
    elem = issue.get("element") or issue.get("selector")
    # Verify selector targets the unwrapped cluster, not body
    assert elem != "<body>" and elem != "body", f"Selector should not be 'body', was: {elem}"
    assert "nav" in str(elem).lower()
    assert "class=\"nav\"" in issue["html_snippet"] or "About" in issue["html_snippet"]


def test_no_nav_landmark_not_emitted_when_no_links():
    """If a page has no navigation links at all, no-nav-landmark should NOT fire."""
    html = """<!DOCTYPE html>
    <html lang="en">
    <head><title>Simple Text Article</title></head>
    <body>
      <main>
        <h1>Single Article</h1>
        <p>This is a standalone article with zero navigational links.</p>
      </main>
    </body>
    </html>"""
    checker = StaticChecker(html, "https://example.com")
    issues = checker.check_landmarks()
    
    nav_issues = [i for i in issues if i["rule_id"] == "no-nav-landmark"]
    assert len(nav_issues) == 0, "no-nav-landmark should not fire when page has < 2 navigation links"


def test_nav_element_satisfies_landmark_check():
    """Proper <nav> landmark with links does not fire no-nav-landmark."""
    html = """<!DOCTYPE html>
    <html lang="en">
    <head><title>Portfolio</title></head>
    <body>
      <nav aria-label="Main Navigation">
        <a href="#about">About</a>
        <a href="#work">Work</a>
      </nav>
      <main>
        <h1>Portfolio</h1>
      </main>
    </body>
    </html>"""
    checker = StaticChecker(html, "https://example.com")
    issues = checker.check_landmarks()
    
    nav_issues = [i for i in issues if i["rule_id"] == "no-nav-landmark"]
    assert len(nav_issues) == 0, "Proper <nav> element should satisfy navigation landmark check"


def test_normalizer_attaches_wcag_relationship_supporting_technique():
    """Verify normalizer assigns supporting_technique and direct_failure=False to no-nav-landmark."""
    raw_issue = {
        "rule_id": "no-nav-landmark",
        "description": "Page has navigation link cluster not wrapped in a <nav> landmark.",
        "element": "div.nav",
        "html_snippet": "<div class=\"nav\"><a href=\"/a\">A</a><a href=\"/b\">B</a></div>",
        "severity": "minor",
        "wcag_criterion": "1.3.1",
        "category": "Structure",
    }
    normalized = normalize_all([raw_issue], [], [], [], "https://example.com")
    assert len(normalized) == 1
    enriched = normalized[0]
    
    # Check conformance classification
    assert enriched["conformance_type"] == "supporting_technique"
    assert "wcag_relationship" in enriched
    rel = enriched["wcag_relationship"]
    assert rel["criterion"] == "1.3.1"
    assert rel["relationship"] == "supports"
    assert rel["direct_failure"] is False
    assert "H97" in rel.get("technique_ref", "")
    
    # Check that WCAG display shows technique context
    assert "Supporting Technique" in enriched["wcag_display"]
    
    # Check that concrete impact summary was assigned (disability-centered)
    assert "screen reader" in enriched["impact_summary"].lower()
    assert "landmarks" in enriched["impact_summary"].lower()


def test_normative_rule_has_direct_failure_true():
    """Verify normative rules (like missing-alt, color-contrast) are marked normative with direct_failure=True."""
    raw_issue = {
        "rule_id": "missing-alt",
        "description": "Image is missing an alt attribute.",
        "element": "img#hero",
        "html_snippet": "<img id=\"hero\" src=\"hero.jpg\">",
        "severity": "critical",
        "wcag_criterion": "1.1.1",
        "category": "Media",
    }
    normalized = normalize_all([raw_issue], [], [], [], "https://example.com")
    assert len(normalized) == 1
    enriched = normalized[0]
    
    assert enriched["conformance_type"] == "normative"
    rel = enriched["wcag_relationship"]
    assert rel["criterion"] == "1.1.1"
    assert rel["relationship"] == "fails"
    assert rel["direct_failure"] is True
    assert enriched["wcag_display"] == "WCAG 1.1.1 (Normative Violation)"


def test_header_and_footer_cluster_detection():
    """Unwrapped header and footer div clusters target their respective containers."""
    html = """<!DOCTYPE html>
    <html lang="en">
    <head><title>Portfolio</title></head>
    <body>
      <div class="site-header">
        <h1>Site Branding</h1>
      </div>
      <div id="main-content">
        <p>Main content paragraphs here with detailed information.</p>
      </div>
      <div class="site-footer">
        <p>&copy; 2026 Company Inc.</p>
      </div>
    </body>
    </html>"""
    checker = StaticChecker(html, "https://example.com")
    issues = checker.check_landmarks()
    
    header_issues = [i for i in issues if i["rule_id"] == "no-header-landmark"]
    assert len(header_issues) == 1
    assert "site-header" in header_issues[0]["element"]
    
    footer_issues = [i for i in issues if i["rule_id"] == "no-footer-landmark"]
    assert len(footer_issues) == 1
    assert "site-footer" in footer_issues[0]["element"]


def test_decoupled_dom_extraction_classification():
    """Verify document_completeness_score distinguishes complete SSR HTML from empty JS shells."""
    from app.services.confidence import document_completeness_score
    from bs4 import BeautifulSoup
    
    # Complete SSR DOM
    ssr_html = """<!DOCTYPE html><html lang="en"><head><title>Sai Portfolio</title></head>
    <body><header><nav><a href="#work">Work</a><a href="#about">About</a></nav></header>
    <main><h1>Full Portfolio</h1><p>Full project details, experience, skills, and contact form.</p></main>
    <footer><p>&copy; 2026 Sai</p></footer></body></html>"""
    
    score_ssr = document_completeness_score(ssr_html)
    assert score_ssr >= 0.50, f"Expected high completeness for SSR HTML, got {score_ssr}"
    
    # Empty JS skeleton shell
    shell_html = """<!DOCTYPE html><html><head><title>App</title></head><body><div id="root"></div></body></html>"""
    text_content = BeautifulSoup(shell_html, "html.parser").get_text(strip=True)
    assert len(shell_html.strip()) < 300
    assert len(text_content) < 30

