"""
Test suite for BEACON AI Adjudication, Context Extraction, Confidence, and Clustering Pipeline.
"""
from app.services.adjudicator import _pre_adjudicate_fast_path
from app.services.confidence import (
    apply_confidence_rules,
    compute_calibrated_confidence_breakdown,
)
from app.services.dom_context import DOMContextExtractor
from app.services.grouper import cluster_root_causes
from app.services.static_checks import StaticChecker


def test_confidence_breakdown():
    """Verify that all 5 calibrated confidence sub-scores are calculated."""
    issue = {
        "rule_id": "image-alt",
        "wcag_criterion": "1.1.1",
        "severity": "critical",
        "confidence_sources": ["axe-core", "static"],
        "element": "img#logo",
        "html_snippet": '<img id="logo" src="logo.png">',
    }
    breakdown = compute_calibrated_confidence_breakdown(issue)
    assert "scanner_confidence" in breakdown
    assert "verification_confidence" in breakdown
    assert "wcag_mapping_confidence" in breakdown
    assert "consensus_confidence" in breakdown
    assert "final_confidence" in breakdown

    assert 0.0 <= breakdown["scanner_confidence"] <= 1.0
    assert 0.0 <= breakdown["verification_confidence"] <= 1.0
    assert 0.0 <= breakdown["wcag_mapping_confidence"] <= 1.0
    assert 0.0 <= breakdown["consensus_confidence"] <= 1.0
    assert 0.0 <= breakdown["final_confidence"] <= 1.0

    # Test applying confidence rules attaches fields to the issue
    issues = [issue]
    result = apply_confidence_rules(issues)
    assert result[0]["scanner_confidence"] > 0.5
    assert result[0]["wcag_mapping_confidence"] >= 0.90
    assert result[0]["confidence_breakdown"] is not None


def test_dom_context_extraction_link():
    """Verify DOMContextExtractor extracts enclosing sentence, heading, and landmarks."""
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
      <main>
        <h2>Annual Financial Reports</h2>
        <p>You can inspect our detailed audited report for fiscal year 2024 by clicking <a id="link1" href="/report.pdf">Learn more</a> here.</p>
      </main>
    </body>
    </html>
    """
    extractor = DOMContextExtractor(html)
    ctx = extractor.extract_link_context("a#link1", '<a id="link1" href="/report.pdf">Learn more</a>')

    assert ctx["link_text"] == "Learn more"
    assert "audited report for fiscal year 2024" in ctx["enclosing_sentence"]
    assert ctx["preceding_heading"] is not None
    assert ctx["preceding_heading"]["text"] == "Annual Financial Reports"
    assert ctx["nearest_landmark"] == "main"
    assert ctx["has_context"] is True


def test_adjudication_fast_path_wcag_244_learn_more():
    """Verify WCAG 2.4.4 fast path recognizes contextual clarity for 'Learn more'."""
    # Case A: Enclosing sentence clarifies destination -> PASS
    dom_context_pass = {
        "link_context": {
            "link_text": "Learn more",
            "enclosing_sentence": "To review the full terms and privacy agreement for your enterprise account, please click Learn more.",
            "preceding_heading": None,
            "aria_label": "",
            "has_context": True,
        }
    }
    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "html_snippet": "<a>Learn more</a>",
    }
    verdict = _pre_adjudicate_fast_path(issue, dom_context_pass)
    assert verdict is not None
    assert verdict.verdict == "pass"
    assert "Enclosing sentence provides clear programmatic context" in verdict.evidence_against[0]

    # Case B: Preceding heading clarifies destination -> PASS
    dom_context_heading = {
        "link_context": {
            "link_text": "Read more",
            "enclosing_sentence": "",
            "preceding_heading": {"text": "Security Vulnerability Advisory CVE-2024-1234"},
            "aria_label": "",
            "has_context": True,
        }
    }
    verdict_h = _pre_adjudicate_fast_path(issue, dom_context_heading)
    assert verdict_h is not None
    assert verdict_h.verdict == "pass"
    assert "Preceding heading provides programmatic context" in verdict_h.evidence_against[0]


def test_form_label_fast_path():
    """Verify form control with valid label wrapping or association is marked PASS."""
    dom_context_labeled = {
        "form_context": {
            "has_label": True,
            "label_text": "Email Address",
            "enclosing_label": True,
            "aria_label": "",
        }
    }
    issue = {
        "rule_id": "missing-label",
        "wcag_criterion": "1.3.1",
        "html_snippet": "<input type='email'>",
    }
    verdict = _pre_adjudicate_fast_path(issue, dom_context_labeled)
    assert verdict is not None
    assert verdict.verdict == "pass"
    assert "wrapping <label>" in verdict.evidence_against[0]


def test_bypass_blocks_decision_tree():
    """Verify WCAG 2.4.1 bypass blocks logic accurately handles repeated blocks and landmarks."""
    # Case 1: Simple landing page / fixture with no navigation -> NO skip link violation
    simple_html = """
    <!DOCTYPE html>
    <html><body><p>Welcome to our simple page.</p></body></html>
    """
    checker = StaticChecker(simple_html, "http://test.local")
    issues = checker.check_skip_nav()
    assert len(issues) == 0

    # Case 2: Multi-link navigation block WITH <main> landmark -> NO violation (landmarks satisfy bypass)
    main_landmark_html = """
    <!DOCTYPE html>
    <html><body>
      <nav>
        <a href="/home">Home</a>
        <a href="/about">About</a>
        <a href="/products">Products</a>
        <a href="/contact">Contact</a>
        <a href="/blog">Blog</a>
      </nav>
      <main>
        <h1>Main Content Header</h1>
        <p>This is the primary content.</p>
      </main>
    </body></html>
    """
    checker_main = StaticChecker(main_landmark_html, "http://test.local")
    issues_main = checker_main.check_skip_nav()
    assert len(issues_main) == 0

    # Case 3: Repeated navigation blocks and NO skip link, NO main landmark, NO h1 -> Violation
    failing_html = """
    <!DOCTYPE html>
    <html><body>
      <header>
        <nav>
          <a href="/1">Link 1</a>
          <a href="/2">Link 2</a>
          <a href="/3">Link 3</a>
          <a href="/4">Link 4</a>
          <a href="/5">Link 5</a>
        </nav>
      </header>
      <div>
        <p>Unstructured content with no landmarks or primary headings.</p>
      </div>
    </body></html>
    """
    checker_fail = StaticChecker(failing_html, "http://test.local")
    issues_fail = checker_fail.check_skip_nav()
    assert len(issues_fail) == 1
    assert issues_fail[0]["rule_id"] == "missing-skip-link"
    assert issues_fail[0]["wcag_criterion"] == "2.4.1"


def test_root_cause_clustering():
    """Verify 5 raw landmark detections are clustered into 1 primary WCAG 1.3.1 finding."""
    raw_detections = [
        {"rule_id": "region", "element": "body", "wcag_criterion": "1.3.1", "confidence_sources": ["axe-core"]},
        {"rule_id": "aria_content_in_landmark", "element": "body", "wcag_criterion": "1.3.1", "confidence_sources": ["axe-core"]},
        {"rule_id": "no-main-landmark", "element": "body", "wcag_criterion": "1.3.1", "confidence_sources": ["static"]},
        {"rule_id": "landmark-roles", "element": "body", "wcag_criterion": "1.3.1", "confidence_sources": ["axe-core"]},
        {"rule_id": "landmark-one-main", "element": "body", "wcag_criterion": "1.3.1", "confidence_sources": ["axe-core"]},
        {"rule_id": "image-alt", "element": "img#avatar", "wcag_criterion": "1.1.1", "confidence_sources": ["axe-core"]},
    ]

    primary_issues, secondary_issues = cluster_root_causes(raw_detections)

    # 5 landmark issues clustered into 1 primary + 4 secondary
    # + 1 image-alt issue = 2 primary issues total!
    assert len(primary_issues) == 2
    assert len(secondary_issues) == 4

    landmark_primary = next(i for i in primary_issues if "landmark" in i["rule_id"])
    assert landmark_primary["group_id"] == "structure:main-landmark"
    assert landmark_primary["is_root_cause_primary"] is True
    assert landmark_primary["wcag_criterion"] == "1.3.1"
    assert "Primary content is not clearly exposed through a main landmark" in landmark_primary["description"]
    assert len(landmark_primary["contributing_rules"]) == 5
    assert set(landmark_primary["confidence_sources"]) == {"axe-core", "static"}
