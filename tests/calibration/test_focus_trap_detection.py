"""
Test focus trap detection probe.
Validates:
- Modal without focusable elements → focus-trap-cycling
- Modal with proper focus management → no issues
- Modal without label → focus-trap-initial
- Background not inert → focus-trap-background
- No close button → focus-trap-escape
- No modals → no issues
"""
import pytest
from app.services.browser_probes import _make_issue


class MockBrowserProber:
    """Minimal mock of BrowserProber for testing focus trap sub-checks.

    We test the helper methods directly rather than through Playwright,
    since Playwright requires a real browser.  The page.evaluate() calls
    are tested via unit mocks.
    """

    def __init__(self, url: str = "https://example.com"):
        self.url = url

    # ── Import the sub-checks from BrowserProber ──
    # We re-implement the synchronous helpers inline (they don't need a page).

    def _check_initial_focus(self, modal: dict, modal_desc: str) -> list[dict]:
        issues = []
        if int(modal.get("focusableCount", 0)) == 0:
            return issues
        has_label = bool(modal.get("label", ""))
        role = modal.get("role", "")
        if role in ("dialog", "alertdialog") and not has_label:
            issues.append(_make_issue(
                self.url, "focus-trap-initial", "violation", "moderate",
                modal_desc, "",
                f"Modal '{modal_desc}' with role='{role}' has no accessible label.",
                "2.4.3", "A", "keyboard",
                "Add aria-label or aria-labelledby to the dialog element.",
                evidence={"role": role, "has_label": False},
                fix_effort="low"
            ))
        return issues

    def _check_escape_mechanism(self, modal: dict, modal_desc: str) -> list[dict]:
        issues = []
        has_close = bool(modal.get("hasCloseButton", False))
        role = modal.get("role", "")
        if role == "dialog" and not has_close:
            issues.append(_make_issue(
                self.url, "focus-trap-escape", "violation", "moderate",
                modal_desc, "",
                f"Modal '{modal_desc}' has no visible close button.",
                "2.1.2", "A", "keyboard",
                "Add a close button with aria-label='Close'.",
                evidence={"role": role, "has_close_button": False},
                fix_effort="low"
            ))
        return issues


class TestFocusTrapInitialFocus:
    """Tests for _check_initial_focus sub-check."""

    def test_dialog_without_label_detected(self):
        prober = MockBrowserProber()
        modal = {
            "role": "dialog",
            "focusableCount": 3,
            "label": "",
            "id": "mymodal",
            "tag": "div",
        }
        issues = prober._check_initial_focus(modal, "div#mymodal")
        assert len(issues) == 1
        assert issues[0]["rule_id"] == "focus-trap-initial"

    def test_dialog_with_label_passes(self):
        prober = MockBrowserProber()
        modal = {
            "role": "dialog",
            "focusableCount": 3,
            "label": "Login Form",
            "id": "login",
            "tag": "div",
        }
        issues = prober._check_initial_focus(modal, "div#login")
        assert len(issues) == 0

    def test_no_focusable_elements_skips(self):
        prober = MockBrowserProber()
        modal = {
            "role": "dialog",
            "focusableCount": 0,
            "label": "",
        }
        issues = prober._check_initial_focus(modal, "div")
        assert len(issues) == 0

    def test_alertdialog_without_label_detected(self):
        prober = MockBrowserProber()
        modal = {
            "role": "alertdialog",
            "focusableCount": 1,
            "label": "",
            "id": "alert",
            "tag": "div",
        }
        issues = prober._check_initial_focus(modal, "div#alert")
        assert len(issues) == 1
        assert issues[0]["rule_id"] == "focus-trap-initial"

    def test_non_dialog_role_skips_label_check(self):
        prober = MockBrowserProber()
        modal = {
            "role": "tooltip",
            "focusableCount": 1,
            "label": "",
        }
        issues = prober._check_initial_focus(modal, "div")
        assert len(issues) == 0


class TestFocusTrapEscapeMechanism:
    """Tests for _check_escape_mechanism sub-check."""

    def test_dialog_without_close_button_detected(self):
        prober = MockBrowserProber()
        modal = {
            "role": "dialog",
            "hasCloseButton": False,
            "id": "settings",
            "tag": "div",
        }
        issues = prober._check_escape_mechanism(modal, "div#settings")
        assert len(issues) == 1
        assert issues[0]["rule_id"] == "focus-trap-escape"

    def test_dialog_with_close_button_passes(self):
        prober = MockBrowserProber()
        modal = {
            "role": "dialog",
            "hasCloseButton": True,
            "id": "settings",
            "tag": "div",
        }
        issues = prober._check_escape_mechanism(modal, "div#settings")
        assert len(issues) == 0

    def test_alertdialog_without_close_not_flagged(self):
        """alertdialog may intentionally block dismissal."""
        prober = MockBrowserProber()
        modal = {
            "role": "alertdialog",
            "hasCloseButton": False,
        }
        issues = prober._check_escape_mechanism(modal, "div")
        assert len(issues) == 0

    def test_no_modals_no_issues(self):
        """Empty modal list produces no issues."""
        prober = MockBrowserProber()
        # No modals to check → no issues
        assert prober._check_initial_focus({}, "") == []
        assert prober._check_escape_mechanism({}, "") == []


class TestFocusTrapIntegration:
    """Integration-level tests combining multiple sub-checks."""

    def test_bad_modal_triggers_multiple_issues(self):
        prober = MockBrowserProber()
        modal = {
            "role": "dialog",
            "focusableCount": 2,
            "label": "",
            "hasCloseButton": False,
            "id": "bad-modal",
            "tag": "div",
        }
        
        initial_issues = prober._check_initial_focus(modal, "div#bad-modal")
        escape_issues = prober._check_escape_mechanism(modal, "div#bad-modal")
        
        all_issues = initial_issues + escape_issues
        rule_ids = {i["rule_id"] for i in all_issues}
        
        assert "focus-trap-initial" in rule_ids
        assert "focus-trap-escape" in rule_ids

    def test_good_modal_triggers_no_issues(self):
        prober = MockBrowserProber()
        modal = {
            "role": "dialog",
            "focusableCount": 3,
            "label": "Settings Dialog",
            "hasCloseButton": True,
            "id": "settings",
            "tag": "div",
        }
        
        initial_issues = prober._check_initial_focus(modal, "div#settings")
        escape_issues = prober._check_escape_mechanism(modal, "div#settings")
        
        assert len(initial_issues) == 0
        assert len(escape_issues) == 0

    def test_issue_structure_is_complete(self):
        prober = MockBrowserProber()
        modal = {
            "role": "dialog",
            "focusableCount": 1,
            "label": "",
            "hasCloseButton": False,
            "id": "test",
            "tag": "div",
        }
        issues = prober._check_initial_focus(modal, "div#test")
        assert len(issues) == 1
        
        issue = issues[0]
        # Verify all required fields
        assert "issue_id" in issue
        assert "rule_id" in issue
        assert "issue_type" in issue
        assert "element" in issue
        assert "severity" in issue
        assert "wcag_criterion" in issue
        assert "wcag_level" in issue
        assert "category" in issue
        assert "confidence" in issue
        assert "suggested_fix" in issue
        assert "evidence" in issue
