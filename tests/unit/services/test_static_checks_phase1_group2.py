import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from app.services.static_checks import StaticChecker


def _run_checks(html: str, checks: list[str]):
    checker = StaticChecker(html, "https://example.test")
    issues = checker.run_all(checks=checks)
    return issues, checker.get_rule_activity()


def _rule_ids(issues: list[dict]) -> set[str]:
    return {issue.get("rule_id", "") for issue in issues}


# ── missing-h1 ───────────────────────────────────────────────────────────────

def test_missing_h1_valid_case():
    html = """
    <html><body>
      <h1>Main page heading</h1>
      <h2>Section</h2>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "missing-h1" not in _rule_ids(issues)
    assert activity["missing-h1"]["violations_found"] == 0


def test_missing_h1_invalid_case():
    html = """
    <html><body>
      <h2>Section heading only</h2>
      <h3>Nested subsection</h3>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "missing-h1" in _rule_ids(issues)
    assert activity["missing-h1"]["violations_found"] == 1
    assert activity["missing-h1"]["confidence_bucket"]["high"] == 1


def test_missing_h1_edge_case_hidden_h1_logged_as_medium():
    html = """
    <html><body>
      <h1 style="display:none">Hidden heading</h1>
      <h2>Visible section heading</h2>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "missing-h1" not in _rule_ids(issues)
    assert activity["missing-h1"]["violations_found"] == 0
    assert activity["missing-h1"]["confidence_bucket"]["medium"] == 1


def test_missing_h1_edge_case_no_headings_skips_rule():
    html = """
    <html><body>
      <p>No headings at all.</p>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "no-headings" in _rule_ids(issues)
    assert "missing-h1" not in _rule_ids(issues)
    assert activity["missing-h1"]["elements_checked"] == 0


# ── multiple-h1 ──────────────────────────────────────────────────────────────

def test_multiple_h1_valid_case():
    html = """
    <html><body>
      <h1>Main heading</h1>
      <h2>Section</h2>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "multiple-h1" not in _rule_ids(issues)
    assert activity["multiple-h1"]["violations_found"] == 0


def test_multiple_h1_invalid_case():
    html = """
    <html><body>
      <h1>Main heading</h1>
      <h1>Another top heading</h1>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "multiple-h1" in _rule_ids(issues)
    assert activity["multiple-h1"]["violations_found"] == 1


def test_multiple_h1_edge_sectioning_context_logged_as_medium():
    html = """
    <html><body>
      <article><h1>Article A</h1></article>
      <article><h1>Article B</h1></article>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "multiple-h1" not in _rule_ids(issues)
    assert activity["multiple-h1"]["violations_found"] == 0
    assert activity["multiple-h1"]["confidence_bucket"]["medium"] == 1


def test_multiple_h1_edge_case_non_h1_headings_not_flagged():
    html = """
    <html><body>
      <h1>Main heading</h1>
      <h2>Section A</h2>
      <h2>Section B</h2>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "multiple-h1" not in _rule_ids(issues)
    assert activity["multiple-h1"]["violations_found"] == 0


# ── heading-order ────────────────────────────────────────────────────────────

def test_heading_order_valid_case():
    html = """
    <html><body>
      <h1>Main heading</h1>
      <h2>Section</h2>
      <h3>Subsection</h3>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "heading-order" not in _rule_ids(issues)
    assert activity["heading-order"]["violations_found"] == 0


def test_heading_order_invalid_case():
    html = """
    <html><body>
      <h1>Main heading</h1>
      <h3>Skipped directly to h3</h3>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "heading-order" in _rule_ids(issues)
    assert activity["heading-order"]["violations_found"] == 1


def test_heading_order_edge_case_first_heading_h2_is_allowed():
    html = """
    <html><body>
      <h2>First visible heading is h2</h2>
      <h3>Next heading</h3>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "heading-order" not in _rule_ids(issues)
    assert activity["heading-order"]["violations_found"] == 0


def test_heading_order_edge_case_single_visible_heading_not_penalized():
    html = """
    <html><body>
      <h2>Only one heading</h2>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings"])

    assert "heading-order" not in _rule_ids(issues)
    assert activity["heading-order"]["elements_checked"] == 0


# ── landmark-roles ───────────────────────────────────────────────────────────

def test_landmark_roles_valid_case():
    html = """
    <html><body>
      <header>Header</header>
      <nav aria-label="Primary navigation"></nav>
      <main>Main content</main>
      <footer>Footer</footer>
    </body></html>
    """
    issues, activity = _run_checks(html, ["landmarks"])

    assert "landmark-roles" not in _rule_ids(issues)
    assert activity["landmark-roles"]["violations_found"] == 0


def test_landmark_roles_invalid_multiple_main_landmarks():
    html = """
    <html><body>
      <main>Primary content</main>
      <main>Secondary content incorrectly marked as main</main>
    </body></html>
    """
    issues, activity = _run_checks(html, ["landmarks"])

    assert "landmark-roles" in _rule_ids(issues)
    assert activity["landmark-roles"]["violations_found"] == 1


def test_landmark_roles_invalid_missing_main_landmark():
    html = """
    <html><body>
      <nav aria-label="Site navigation"></nav>
      <section>Content without main landmark</section>
    </body></html>
    """
    issues, activity = _run_checks(html, ["landmarks"])

    assert "landmark-roles" in _rule_ids(issues)
    assert activity["landmark-roles"]["violations_found"] == 1
    assert activity["landmark-roles"]["confidence_bucket"]["high"] == 1


def test_landmark_roles_edge_multiple_unlabeled_navs_logged_as_medium():
    html = """
    <html><body>
      <main>Main content</main>
      <nav><a href="#a">A</a></nav>
      <nav><a href="#b">B</a></nav>
    </body></html>
    """
    issues, activity = _run_checks(html, ["landmarks"])

    assert "landmark-roles" not in _rule_ids(issues)
    assert activity["landmark-roles"]["violations_found"] == 0
    assert activity["landmark-roles"]["confidence_bucket"]["medium"] == 1


# ── button-name ──────────────────────────────────────────────────────────────

def test_button_name_valid_case():
    html = """
    <html><body>
      <button type="button">Save</button>
    </body></html>
    """
    issues, activity = _run_checks(html, ["buttons"])

    assert "button-name" not in _rule_ids(issues)
    assert activity["button-name"]["violations_found"] == 0


def test_button_name_invalid_case():
    html = """
    <html><body>
      <button type="button"></button>
    </body></html>
    """
    issues, activity = _run_checks(html, ["buttons"])

    assert "button-name" in _rule_ids(issues)
    assert activity["button-name"]["violations_found"] == 1


def test_button_name_edge_invalid_aria_labelledby_reference_is_flagged():
    html = """
    <html><body>
      <button aria-labelledby="missing-id"></button>
    </body></html>
    """
    issues, activity = _run_checks(html, ["buttons"])

    assert "button-name" in _rule_ids(issues)
    assert activity["button-name"]["violations_found"] == 1


def test_button_name_edge_icon_only_button_logged_as_medium():
    html = """
    <html><body>
      <button type="button"><svg><path d="M0 0"/></svg></button>
    </body></html>
    """
    issues, activity = _run_checks(html, ["buttons"])

    assert "button-name" not in _rule_ids(issues)
    assert activity["button-name"]["violations_found"] == 0
    assert activity["button-name"]["confidence_bucket"]["medium"] == 1


def test_group2_rule_activity_contains_confidence_buckets():
    html = """
    <html><body>
      <h2>Section heading only</h2>
      <h4>Skipped heading</h4>
      <main>Primary</main>
      <main>Duplicate main</main>
      <button></button>
    </body></html>
    """
    issues, activity = _run_checks(html, ["headings", "landmarks", "buttons"])

    assert "missing-h1" in _rule_ids(issues)
    assert "heading-order" in _rule_ids(issues)
    assert "landmark-roles" in _rule_ids(issues)
    assert "button-name" in _rule_ids(issues)

    for rule_id in ["missing-h1", "multiple-h1", "heading-order", "landmark-roles", "button-name"]:
        assert "confidence_bucket" in activity[rule_id]
        assert set(activity[rule_id]["confidence_bucket"].keys()) == {"high", "medium", "low"}
