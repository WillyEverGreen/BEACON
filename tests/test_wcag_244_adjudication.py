"""
Mandatory regression test suite for WCAG 2.4.4 (Link Purpose in Context).
Validates:
- Case A: Contextual PASS (enclosing sentence or proximate heading)
- Case B: Descriptive link text PASS
- Case C1: Insufficient context with complete DOM -> FAIL
- Case C2: Insufficient context with incomplete DOM -> NEEDS_REVIEW
- Case D: ARIA label context PASS (aria-label, aria-labelledby)
- Edge cases: Distant non-proximate heading (e.g. footer vs main), empty link
"""
from app.services.adjudicator import _pre_adjudicate_fast_path
from app.services.dom_context import DOMContextExtractor


def test_wcag_244_case_a_contextual_heading_pass():
    """Case A1: Generic link accompanied by proximate section heading -> PASS."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
      <head><title>Pricing Plans</title></head>
      <body>
        <main>
          <section id="pricing-section">
            <h2>Pricing</h2>
            <p>Compare plans and features for enterprise teams.</p>
            <a id="btn-pricing" href="/pricing">Learn more</a>
          </section>
        </main>
      </body>
    </html>
    """
    extractor = DOMContextExtractor(html)
    dom_ctx = extractor.extract_context_for_issue({
        "rule_id": "generic-link-text",
        "element": "a#btn-pricing",
        "html_snippet": '<a id="btn-pricing" href="/pricing">Learn more</a>',
    })

    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "html_snippet": '<a id="btn-pricing" href="/pricing">Learn more</a>',
    }
    result = _pre_adjudicate_fast_path(issue, dom_ctx)
    assert result is not None
    assert result.verdict == "pass"
    assert result.wcag_criterion == "2.4.4"
    assert any("heading" in ev.lower() or "sentence" in ev.lower() for ev in result.evidence_against)


def test_wcag_244_case_a_short_semantic_sentence_pass():
    """Case A2: Short informative sentence (< 20 chars) identifies purpose -> PASS (Correction 1)."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
      <body>
        <p id="p-view">View pricing. <a id="link-short" href="/pricing">Learn more</a></p>
      </body>
    </html>
    """
    extractor = DOMContextExtractor(html)
    dom_ctx = extractor.extract_context_for_issue({
        "rule_id": "generic-link-text",
        "element": "a#link-short",
        "html_snippet": '<a id="link-short" href="/pricing">Learn more</a>',
    })

    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "html_snippet": '<a id="link-short" href="/pricing">Learn more</a>',
    }
    result = _pre_adjudicate_fast_path(issue, dom_ctx)
    assert result is not None
    assert result.verdict == "pass"


def test_wcag_244_case_b_descriptive_link_text_pass():
    """Case B: Link text itself describes purpose -> PASS."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
      <body>
        <a id="link-desc" href="/pricing">Learn more about pricing</a>
      </body>
    </html>
    """
    extractor = DOMContextExtractor(html)
    dom_ctx = extractor.extract_context_for_issue({
        "rule_id": "generic-link-text",
        "element": "a#link-desc",
        "html_snippet": '<a id="link-desc" href="/pricing">Learn more about pricing</a>',
    })

    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "html_snippet": '<a id="link-desc" href="/pricing">Learn more about pricing</a>',
    }
    result = _pre_adjudicate_fast_path(issue, dom_ctx)
    assert result is not None
    assert result.verdict == "pass"
    assert "descriptive" in result.evidence_against[0].lower()


def test_wcag_244_case_c1_insufficient_context_complete_dom_fail():
    """Case C1: Generic link with no context in a complete DOM -> FAIL (Correction 4)."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
      <head><title>Test Page</title></head>
      <body>
        <div>
          <a id="link-isolated" href="/pricing">Learn more</a>
        </div>
      </body>
    </html>
    """
    extractor = DOMContextExtractor(html)
    dom_ctx = extractor.extract_context_for_issue({
        "rule_id": "generic-link-text",
        "element": "a#link-isolated",
        "html_snippet": '<a id="link-isolated" href="/pricing">Learn more</a>',
    })

    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "html_snippet": '<a id="link-isolated" href="/pricing">Learn more</a>',
    }
    result = _pre_adjudicate_fast_path(issue, dom_ctx)
    assert result is not None
    assert result.verdict == "fail"
    assert result.confidence >= 0.85
    assert len(result.evidence_for) > 0


def test_wcag_244_case_c2_incomplete_dom_needs_review():
    """Case C2: Generic link with no surrounding DOM provided -> NEEDS_REVIEW (Correction 4)."""
    # Bare HTML snippet only — BEACON wasn't given full DOM
    bare_html = '<a href="/pricing">Learn more</a>'
    extractor = DOMContextExtractor(bare_html)
    dom_ctx = extractor.extract_context_for_issue({
        "rule_id": "generic-link-text",
        "element": "a",
        "html_snippet": '<a href="/pricing">Learn more</a>',
    })

    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "html_snippet": '<a href="/pricing">Learn more</a>',
    }
    result = _pre_adjudicate_fast_path(issue, dom_ctx)
    assert result is not None
    assert result.verdict == "needs_review"
    assert "surrounding page dom" in result.missing_evidence[0].lower()


def test_wcag_244_case_d_aria_label_pass():
    """Case D: Generic link text with valid descriptive aria-label -> PASS."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
      <body>
        <a id="link-aria" href="/pricing" aria-label="Learn more about enterprise pricing">
          Learn more
        </a>
      </body>
    </html>
    """
    extractor = DOMContextExtractor(html)
    dom_ctx = extractor.extract_context_for_issue({
        "rule_id": "generic-link-text",
        "element": "a#link-aria",
        "html_snippet": '<a id="link-aria" href="/pricing" aria-label="Learn more about enterprise pricing">Learn more</a>',
    })

    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "html_snippet": '<a id="link-aria" href="/pricing" aria-label="Learn more about enterprise pricing">Learn more</a>',
    }
    result = _pre_adjudicate_fast_path(issue, dom_ctx)
    assert result is not None
    assert result.verdict == "pass"
    assert "aria-label" in result.evidence_against[0]


def test_wcag_244_case_d_aria_labelledby_pass():
    """Case D2: Generic link with aria-labelledby referencing descriptive heading -> PASS."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
      <body>
        <h3 id="plan-title">Pro Developer Subscription</h3>
        <a id="link-by" href="/pro" aria-labelledby="plan-title">Learn more</a>
      </body>
    </html>
    """
    extractor = DOMContextExtractor(html)
    dom_ctx = extractor.extract_context_for_issue({
        "rule_id": "generic-link-text",
        "element": "a#link-by",
        "html_snippet": '<a id="link-by" href="/pro" aria-labelledby="plan-title">Learn more</a>',
    })

    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "html_snippet": '<a id="link-by" href="/pro" aria-labelledby="plan-title">Learn more</a>',
    }
    result = _pre_adjudicate_fast_path(issue, dom_ctx)
    assert result is not None
    assert result.verdict == "pass"
    assert "Pro Developer Subscription" in result.evidence_against[0]


def test_wcag_244_distant_heading_not_proximate():
    """Verify that a distant heading in <main> is NOT accepted as context for an isolated link in <footer>."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
      <head><title>Test</title></head>
      <body>
        <main>
          <h2>Our Core Products</h2>
          <p>Description of core products.</p>
        </main>
        <footer>
          <a id="footer-link" href="/terms">Learn more</a>
        </footer>
      </body>
    </html>
    """
    extractor = DOMContextExtractor(html)
    dom_ctx = extractor.extract_context_for_issue({
        "rule_id": "generic-link-text",
        "element": "a#footer-link",
        "html_snippet": '<a id="footer-link" href="/terms">Learn more</a>',
    })

    # Preceding heading should be None because footer and main are isolated landmarks
    assert dom_ctx["link_context"]["preceding_heading"] is None

    issue = {
        "rule_id": "generic-link-text",
        "wcag_criterion": "2.4.4",
        "html_snippet": '<a id="footer-link" href="/terms">Learn more</a>',
    }
    result = _pre_adjudicate_fast_path(issue, dom_ctx)
    assert result is not None
    # Complete DOM without proximate context -> FAIL
    assert result.verdict == "fail"


def test_wcag_244_empty_link_fail():
    """Link with no accessible text -> FAIL."""
    html = '<!DOCTYPE html><html><body><a id="empty" href="/x"></a></body></html>'
    extractor = DOMContextExtractor(html)
    dom_ctx = extractor.extract_context_for_issue({
        "rule_id": "empty-link",
        "element": "a#empty",
        "html_snippet": '<a id="empty" href="/x"></a>',
    })
    issue = {
        "rule_id": "empty-link",
        "wcag_criterion": "2.4.4",
        "html_snippet": '<a id="empty" href="/x"></a>',
    }
    result = _pre_adjudicate_fast_path(issue, dom_ctx)
    assert result is not None
    assert result.verdict == "fail"
