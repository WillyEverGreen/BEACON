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
    <html><body>
      <img src="hero.jpg" />
    </body></html>
    """
    issues, activity = _run_checks(html, ["images"])

    assert "missing-alt" in _rule_ids(issues)
    assert activity["missing-alt"]["violations_found"] == 1
    assert activity["missing-alt"]["confidence_bucket"]["high"] == 1


def test_missing_alt_edge_spacer_logged_as_medium():
    html = """
    <html><body>
      <img src="/assets/spacer.gif" width="1" height="1" />
    </body></html>
    """
    issues, activity = _run_checks(html, ["images"])

    assert "missing-alt" not in _rule_ids(issues)
    assert activity["missing-alt"]["violations_found"] == 0
    assert activity["missing-alt"]["confidence_bucket"]["medium"] == 1


def test_missing_alt_empty_alt_logged_as_medium():
    html = """
    <html><body>
      <img src="hero.jpg" alt="" />
    </body></html>
    """
    issues, activity = _run_checks(html, ["images"])

    assert activity["missing-alt"]["violations_found"] == 0
    assert activity["missing-alt"]["confidence_bucket"]["medium"] == 1


# -- input-label ---------------------------------------------------------------


def test_input_label_invalid_case():
    html = """
    <html><body>
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
    <html><body>
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
    <html><body>
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
    <html><body>
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
    <html><body>
      <div onclick="openMenu()">Open</div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["buttons"])

    assert "clickable-no-role" in _rule_ids(issues)
    assert activity["clickable-no-role"]["violations_found"] == 1


def test_clickable_no_role_edge_interactive_child_logged_as_medium():
    html = """
    <html><body>
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
    <html><body>
      <svg><path d="M0 0 L5 5" /></svg>
    </body></html>
    """
    issues, activity = _run_checks(html, ["svg_accessible_name"])

    assert "svg-accessible-name" in _rule_ids(issues)
    assert activity["svg-accessible-name"]["violations_found"] == 1


def test_svg_accessible_name_edge_inside_button_logged_as_medium():
    html = """
    <html><body>
      <button aria-label="Close">
        <svg><path d="M0 0 L5 5" /></svg>
      </button>
    </body></html>
    """
    issues, activity = _run_checks(html, ["svg_accessible_name"])

    assert "svg-accessible-name" not in _rule_ids(issues)
    assert activity["svg-accessible-name"]["violations_found"] == 0
    assert activity["svg-accessible-name"]["confidence_bucket"]["medium"] == 1


# -- missing-lang --------------------------------------------------------------


def test_missing_lang_invalid_case():
    html = """
    <html><body><p>Hello</p></body></html>
    """
    issues, activity = _run_checks(html, ["language"])

    assert "missing-lang" in _rule_ids(issues)
    assert activity["missing-lang"]["violations_found"] == 1


def test_missing_lang_valid_case():
    html = """
    <html lang="en"><body><p>Hello</p></body></html>
    """
    issues, activity = _run_checks(html, ["language"])

    assert "missing-lang" not in _rule_ids(issues)
    assert activity["missing-lang"]["violations_found"] == 0


# -- autocomplete-missing ------------------------------------------------------


def test_autocomplete_missing_invalid_case():
    html = """
    <html><body>
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
    <html><body>
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
    <html><body>
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
    <html><body>
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
    <html><body>
      <img src="hero.jpg" />
      <form>
        <input id="email" name="email" type="email" />
        <label for="zip">ZIP</label>
        <label for="zip">ZIP</label>
        <input id="zip" name="zip" type="text" />
      </form>
      <div onclick="openMenu()">Open</div>
      <svg><path d="M0 0 L5 5" /></svg>
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
        "svg-accessible-name",
        "missing-lang",
        "autocomplete-missing",
        "duplicate-label",
    }

    assert "missing-alt" in _rule_ids(issues)
    assert "input-label" in _rule_ids(issues)
    assert "input-name" in _rule_ids(issues)
    assert "clickable-no-role" in _rule_ids(issues)
    assert "svg-accessible-name" in _rule_ids(issues)
    assert "missing-lang" in _rule_ids(issues)
    assert "autocomplete-missing" in _rule_ids(issues)
    assert "duplicate-label" in _rule_ids(issues)

    for rule_id in expected:
        assert "confidence_bucket" in activity[rule_id]
        assert set(activity[rule_id]["confidence_bucket"].keys()) == {"high", "medium", "low"}
