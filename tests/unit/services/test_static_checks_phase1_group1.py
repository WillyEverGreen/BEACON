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


# ── missing-label ─────────────────────────────────────────────────────────────

def test_missing_label_valid_case():
    html = """
    <html><body>
      <form>
        <label for="email">Email</label>
        <input id="email" name="email" type="email" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "missing-label" not in _rule_ids(issues)
    assert activity["missing-label"]["violations_found"] == 0


def test_missing_label_invalid_case():
    html = """
    <html><body>
      <form>
        <input id="email" name="email" type="email" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "missing-label" in _rule_ids(issues)
    assert activity["missing-label"]["violations_found"] == 1
    assert activity["missing-label"]["confidence_bucket"]["high"] == 1


def test_missing_label_edge_case_hidden_input_ignored():
    html = """
    <html><body>
      <form>
        <input name="csrf" type="hidden" value="x" />
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "missing-label" not in _rule_ids(issues)
    assert activity["missing-label"]["elements_checked"] == 0


def test_missing_label_role_widget_without_name_flagged():
    html = """
    <html><body>
      <form>
        <div role="combobox"></div>
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "missing-label" in _rule_ids(issues)
    assert activity["missing-label"]["violations_found"] == 1


def test_missing_label_role_widget_with_aria_name_not_flagged():
    html = """
    <html><body>
      <form>
        <div role="combobox" aria-label="Country selector"></div>
      </form>
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms"])

    assert "missing-label" not in _rule_ids(issues)
    assert activity["missing-label"]["violations_found"] == 0


# ── aria-required-parent ─────────────────────────────────────────────────────

def test_aria_required_parent_valid_case():
    html = """
    <html><body>
      <div role="listbox">
        <div role="option">Red</div>
      </div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-parent" not in _rule_ids(issues)
    assert activity["aria-required-parent"]["violations_found"] == 0


def test_aria_required_parent_invalid_case():
    html = """
    <html><body>
      <div role="option">Red</div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-parent" in _rule_ids(issues)
    assert activity["aria-required-parent"]["violations_found"] == 1
    assert activity["aria-required-parent"]["confidence_bucket"]["high"] == 1


def test_aria_required_parent_edge_case_nested_group_supported():
    html = """
    <html><body>
      <div role="listbox">
        <div role="group">
          <div role="option">Blue</div>
        </div>
      </div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-parent" not in _rule_ids(issues)
    assert activity["aria-required-parent"]["violations_found"] == 0


def test_aria_required_parent_listitem_valid_inside_list():
    html = """
    <html><body>
      <div role="list">
        <div role="listitem">Item A</div>
      </div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-parent" not in _rule_ids(issues)
    assert activity["aria-required-parent"]["violations_found"] == 0


def test_aria_required_parent_listitem_without_list_flagged():
    html = """
    <html><body>
      <div role="listitem">Orphan item</div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-parent" in _rule_ids(issues)
    assert activity["aria-required-parent"]["violations_found"] == 1


# ── aria-required-children ───────────────────────────────────────────────────

def test_aria_required_children_valid_case():
    html = """
    <html><body>
      <div role="tablist">
        <button role="tab">Overview</button>
      </div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-children" not in _rule_ids(issues)
    assert activity["aria-required-children"]["violations_found"] == 0


def test_aria_required_children_invalid_case():
    html = """
    <html><body>
      <div role="tablist"></div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-children" in _rule_ids(issues)
    assert activity["aria-required-children"]["violations_found"] == 1
    assert activity["aria-required-children"]["confidence_bucket"]["high"] == 1


def test_aria_required_children_edge_case_busy_container_skipped():
    html = """
    <html><body>
      <div role="tablist" aria-busy="true"></div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-children" not in _rule_ids(issues)
    assert activity["aria-required-children"]["violations_found"] == 0


def test_aria_required_children_list_without_items_flagged():
    html = """
    <html><body>
      <div role="list"></div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-children" in _rule_ids(issues)
    assert activity["aria-required-children"]["violations_found"] == 1


def test_aria_required_children_list_with_listitem_valid():
    html = """
    <html><body>
      <div role="list">
        <div role="listitem">Item A</div>
      </div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-required-children" not in _rule_ids(issues)
    assert activity["aria-required-children"]["violations_found"] == 0


# ── aria-allowed-role ────────────────────────────────────────────────────────

def test_aria_allowed_role_valid_case():
    html = """
    <html><body>
      <div role="button">Save</div>
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-allowed-role" not in _rule_ids(issues)
    assert activity["aria-allowed-role"]["violations_found"] == 0


def test_aria_allowed_role_invalid_case():
    html = """
    <html><body>
      <input type="text" role="navigation" />
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-allowed-role" in _rule_ids(issues)
    assert activity["aria-allowed-role"]["violations_found"] == 1
    assert activity["aria-allowed-role"]["confidence_bucket"]["high"] == 1


def test_aria_allowed_role_edge_case_textbox_role_allowed():
    html = """
    <html><body>
      <input type="text" role="textbox" aria-label="Name" />
    </body></html>
    """
    issues, activity = _run_checks(html, ["aria"])

    assert "aria-allowed-role" not in _rule_ids(issues)
    assert activity["aria-allowed-role"]["violations_found"] == 0


# ── link-purpose ─────────────────────────────────────────────────────────────

def test_link_purpose_valid_case():
    html = """
    <html><body>
      <a href="/pricing">View Pricing Plans</a>
    </body></html>
    """
    issues, activity = _run_checks(html, ["links"])

    assert "link-purpose" not in _rule_ids(issues)
    assert activity["link-purpose"]["violations_found"] == 0


def test_link_purpose_invalid_case():
    html = """
    <html><body>
      <a href="/docs">click here</a>
    </body></html>
    """
    issues, activity = _run_checks(html, ["links"])

    assert "link-purpose" in _rule_ids(issues)
    assert activity["link-purpose"]["violations_found"] == 1
    assert activity["link-purpose"]["confidence_bucket"]["medium"] == 1


def test_link_purpose_edge_case_programmatic_name_avoids_flag():
    html = """
    <html><body>
      <a href="/docs" aria-label="Open developer documentation">click here</a>
    </body></html>
    """
    issues, activity = _run_checks(html, ["links"])

    assert "link-purpose" not in _rule_ids(issues)
    assert activity["link-purpose"]["violations_found"] == 0


def test_link_purpose_identical_ambiguous_names_different_destinations_flagged():
    html = """
    <html><body>
      <nav>
        <a href="/about/contact">Contact us</a>
        <a href="/careers/contact">Contact us</a>
      </nav>
    </body></html>
    """
    issues, activity = _run_checks(html, ["links"])

    assert "link-purpose" in _rule_ids(issues)
    assert activity["link-purpose"]["violations_found"] == 1


def test_link_purpose_identical_ambiguous_names_same_destination_not_flagged():
    html = """
    <html><body>
      <nav>
        <a href="/contact">Contact us</a>
        <a href="/contact">Contact us</a>
      </nav>
    </body></html>
    """
    issues, activity = _run_checks(html, ["links"])

    assert "link-purpose" not in _rule_ids(issues)
    assert activity["link-purpose"]["violations_found"] == 0


def test_link_purpose_iframe_without_name_flagged():
    html = """
    <html><body>
      <iframe src="/embed/video"></iframe>
    </body></html>
    """
    issues, activity = _run_checks(html, ["links"])

    assert "link-purpose" in _rule_ids(issues)
    assert activity["link-purpose"]["violations_found"] == 1


def test_group1_rule_activity_includes_confidence_bucket_counts():
    html = """
    <html><body>
      <form><input type="text" name="email" /></form>
      <a href="/x">click here</a>
      <div role="option">Standalone option</div>
      <div role="tablist"></div>
      <input type="text" role="navigation" />
    </body></html>
    """
    issues, activity = _run_checks(html, ["forms", "links", "aria"])

    assert "missing-label" in _rule_ids(issues)
    assert "link-purpose" in _rule_ids(issues)
    assert "aria-required-parent" in _rule_ids(issues)
    assert "aria-required-children" in _rule_ids(issues)
    assert "aria-allowed-role" in _rule_ids(issues)

    for rule_id in [
        "missing-label",
        "link-purpose",
        "aria-required-parent",
        "aria-required-children",
        "aria-allowed-role",
    ]:
        assert "confidence_bucket" in activity[rule_id]
        assert set(activity[rule_id]["confidence_bucket"].keys()) == {"high", "medium", "low"}
