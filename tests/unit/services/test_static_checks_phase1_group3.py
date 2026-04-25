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


# -- missing-alt ---------------------------------------------------------------


def test_missing_alt_invalid_case():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <img src="hero.jpg" />
    </body></html>
    """
    issues, activity = _run_checks(html, ["images"])

    assert "missing-alt" in _rule_ids(issues)
    assert activity["missing-alt"]["violations_found"] == 1
    assert activity["missing-alt"]["confidence_bucket"]["high"] == 1


def test_missing_alt_edge_spacer_logged_as_medium():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <img src="/assets/spacer.gif" width="1" height="1" />
    </body></html>
    """
    issues, activity = _run_checks(html, ["images"])

    assert "missing-alt" not in _rule_ids(issues)
    assert activity["missing-alt"]["violations_found"] == 0
    assert activity["missing-alt"]["confidence_bucket"]["medium"] == 1


def test_missing_alt_empty_alt_logged_as_medium():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <img src="hero.jpg" alt="" />
    </body></html>
    """
    issues, activity = _run_checks(html, ["images"])

    assert activity["missing-alt"]["violations_found"] == 0
    assert activity["missing-alt"]["confidence_bucket"]["medium"] == 1


# -- input-label ---------------------------------------------------------------


def test_input_label_invalid_case():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <form>
        <input id="email" name="email" type="email" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "input-label" in _rule_ids(issues)
    assert activity["input-label"]["violations_found"] == 1


def test_input_label_edge_aria_label_only_logged_as_medium():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <form>
        <input id="search" name="search" type="text" aria-label="Search" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "input-label" not in _rule_ids(issues)
    assert activity["input-label"]["violations_found"] == 0
    assert activity["input-label"]["confidence_bucket"]["medium"] == 1


# -- input-name ----------------------------------------------------------------


def test_input_name_invalid_case():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <form>
        <input id="q" type="text" aria-labelledby="missing-id" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "input-name" in _rule_ids(issues)
    assert activity["input-name"]["violations_found"] == 1


def test_input_name_edge_placeholder_logged_as_medium():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <form>
        <input id="q" type="text" placeholder="Search this site" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "input-name" not in _rule_ids(issues)
    assert activity["input-name"]["violations_found"] == 0
    assert activity["input-name"]["confidence_bucket"]["medium"] == 1


# -- clickable-no-role ---------------------------------------------------------


def test_clickable_no_role_invalid_case():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <div onclick="openMenu()">Open</div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["buttons"])

    assert "clickable-no-role" in _rule_ids(issues)
    assert activity["clickable-no-role"]["violations_found"] == 1


def test_clickable_no_role_edge_interactive_child_logged_as_medium():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <div onclick="trackClick()"><a href="/next">Next</a></div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["buttons"])

    assert "clickable-no-role" not in _rule_ids(issues)
    assert activity["clickable-no-role"]["violations_found"] == 0
    assert activity["clickable-no-role"]["confidence_bucket"]["medium"] == 1


# -- svg-accessible-name -------------------------------------------------------


def test_svg_accessible_name_invalid_case():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <p>Page content with an unlabelled SVG below.</p>
      <svg><path d="M0 0 L5 5" /></svg>
    </body></html>
    """
    issues, activity = _run_checks(html, ["svg_accessible_name"])

    assert "svg-no-accessible-name" in _rule_ids(issues)
    assert activity["svg-no-accessible-name"]["violations_found"] == 1


def test_svg_accessible_name_edge_inside_button_logged_as_medium():
    """An SVG inside a labelled button still fires: the SVG element itself has no
    accessible name (no aria-label, aria-labelledby, or <title>). The parent
    button's aria-label does not propagate to the SVG in BEACON's static check.
    This behaviour is intentionally strict — suggest adding aria-hidden="true"
    to purely decorative SVG icons."""
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <p>Page content with a labelled button containing an SVG icon.</p>
      <button aria-label="Close">
        <svg><path d="M0 0 L5 5" /></svg>
      </button>
    </body></html>
    """
    issues, activity = _run_checks(html, ["svg_accessible_name"])

    # SVG has no accessible name of its own — violation is raised.
    # To suppress, use aria-hidden="true" on the decorative SVG.
    assert "svg-no-accessible-name" in _rule_ids(issues)
    assert activity["svg-no-accessible-name"]["violations_found"] == 1


def test_svg_accessible_name_decorative_aria_hidden_suppressed():
    """An SVG marked aria-hidden="true" is treated as decorative and does not fire."""
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <p>Page content with a decorative SVG that is hidden from AT.</p>
      <button aria-label="Close">
        <svg aria-hidden="true"><path d="M0 0 L5 5" /></svg>
      </button>
    </body></html>
    """
    issues, activity = _run_checks(html, ["svg_accessible_name"])

    assert "svg-no-accessible-name" not in _rule_ids(issues)
    assert activity["svg-no-accessible-name"]["violations_found"] == 0
    assert activity["svg-no-accessible-name"]["confidence_bucket"]["medium"] == 1


# -- missing-lang --------------------------------------------------------------


def test_missing_lang_invalid_case():
    html = """
    <html><head><title>Test</title></head><body><p>Hello world paragraph.</p></body></html>
    """
    issues, activity = _run_checks(html, ["language"])

    assert "missing-lang" in _rule_ids(issues)
    assert activity["missing-lang"]["violations_found"] == 1


def test_missing_lang_valid_case():
    html = """
    <html lang="en"><head><title>Test</title></head><body><p>Hello world paragraph.</p></body></html>
    """
    issues, activity = _run_checks(html, ["language"])

    assert "missing-lang" not in _rule_ids(issues)
    assert activity["missing-lang"]["violations_found"] == 0


# -- autocomplete-missing ------------------------------------------------------


def test_autocomplete_missing_invalid_case():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <form>
        <label for="email">Email</label>
        <input id="email" name="email" type="email" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "autocomplete-missing" in _rule_ids(issues)
    assert activity["autocomplete-missing"]["violations_found"] == 1


def test_autocomplete_missing_edge_generic_field_not_flagged():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <form>
        <label for="query">Query</label>
        <input id="query" name="query" type="text" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "autocomplete-missing" not in _rule_ids(issues)
    assert activity["autocomplete-missing"]["violations_found"] == 0


# -- duplicate-label -----------------------------------------------------------


def test_duplicate_label_invalid_case():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <form>
        <label for="zip">ZIP</label>
        <label for="zip">ZIP</label>
        <input id="zip" name="zip" type="text" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "duplicate-label" in _rule_ids(issues)
    assert activity["duplicate-label"]["violations_found"] == 1


def test_duplicate_label_valid_case():
    html = """
    <html lang="en"><head><title>Test</title></head><body>
      <form>
        <label for="zip">ZIP code</label>
        <input id="zip" name="zip" type="text" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "duplicate-label" not in _rule_ids(issues)
    assert activity["duplicate-label"]["violations_found"] == 0


# -- rule_activity shape -------------------------------------------------------


def test_group3_rule_activity_contains_confidence_buckets():
    html = """
    <html><head><title>Test page with multiple violations</title></head><body>
      <p>This page has several accessibility issues for testing purposes.</p>
      <img src="hero.jpg" />
      <form>
        <input id="email" name="email" type="email" />
        <label for="zip">ZIP</label>
        <label for="zip">ZIP</label>
        <input id="zip" name="zip" type="text" />
      </form>
      <div onclick="openMenu()">Open</div>
      <svg aria-hidden="true"><path d="M0 0 L5 5" /></svg>
    </body></html>
    """

    issues, activity = _run_checks(
        html,
        ["images", "forms", "buttons", "svg_accessible_name", "language"],
    )

    expected = {
        "missing-alt",
        "input-label",
        "input-name",
        "clickable-no-role",
        "svg-no-accessible-name",
        "missing-lang",
        "autocomplete-missing",
        "duplicate-label",
    }

    assert "missing-alt" in _rule_ids(issues)
    assert "input-label" in _rule_ids(issues)
    assert "input-name" in _rule_ids(issues)
    assert "clickable-no-role" in _rule_ids(issues)
    # SVG is aria-hidden so no violation; medium signal is logged instead
    assert "svg-no-accessible-name" not in _rule_ids(issues)
    assert activity["svg-no-accessible-name"]["violations_found"] == 0
    assert activity["svg-no-accessible-name"]["confidence_bucket"]["medium"] == 1
    assert "missing-lang" in _rule_ids(issues)
    assert "autocomplete-missing" in _rule_ids(issues)
    assert "duplicate-label" in _rule_ids(issues)

    for rule_id in ["missing-alt", "input-label", "input-name", "clickable-no-role",
                    "svg-no-accessible-name", "missing-lang", "autocomplete-missing", "duplicate-label"]:
        assert "confidence_bucket" in activity[rule_id]
        assert set(activity[rule_id]["confidence_bucket"].keys()) == {"high", "medium", "low"}
