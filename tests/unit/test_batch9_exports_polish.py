"""
Unit tests for Batch 9: Enterprise Exports, Reports, Accessibility Statements & Custom Profiles (§66–§75).
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.audit.exporters.csv_exporter import export_to_csv
from app.main import app
from app.profiles.custom_profiles import (
    CustomProfileDefinition,
    CustomRuleDefinition,
    custom_profile_registry,
)
from app.profiles.engine import evaluate_profile
from app.services.accessibility_statement import generate_accessibility_statement
from app.services.report_generator import generate_enterprise_audit_report


@pytest.fixture
def sample_audit_data():
    return {
        "id": "scan-999",
        "url": "https://company.org",
        "pages_scanned": 4,
        "issues": [
            {
                "id": "iss-01",
                "rule_id": "image-alt",
                "wcag_criterion": "1.1.1",
                "wcag_level": "A",
                "severity": "critical",
                "verdict": "fail",
                "confidence": 0.96,
                "selector": "img#logo",
                "description": "Logo missing alt text.",
                "suggested_fix": '<img id="logo" alt="Acme Corp">',
                "persona_lenses": [{"id": "SCREEN_READER", "name": "Screen Reader Lens"}],
                "regulatory_mappings": {"GLOBAL_WCAG_22_AA": "SC 1.1.1 Non-text Content"},
            },
            {
                "id": "iss-02",
                "rule_id": "focus-obscured",
                "wcag_criterion": "2.4.11",
                "wcag_level": "AA",
                "severity": "moderate",
                "verdict": "needs_review",
                "confidence": 0.70,
                "selector": "input#search",
                "description": "Focus partially obscured by sticky banner.",
                "persona_lenses": [{"id": "KEYBOARD_MOTOR", "name": "Keyboard & Motor Lens"}],
            },
        ],
    }


# ── §66: Enterprise Exports Tests ─────────────────────────────────────────────

def test_csv_exporter_structure(sample_audit_data):
    """Verify CSV export contains tabular format and required columns (§66)."""
    csv_text = export_to_csv(sample_audit_data["issues"], target_url=sample_audit_data["url"])
    lines = csv_text.strip().splitlines()

    # Verify header line
    assert "Finding ID,Rule ID,WCAG Criterion,WCAG Level,Severity,Verdict" in lines[0]
    assert len(lines) == 3  # Header + 2 data rows

    # Verify content
    assert "iss-01,image-alt,1.1.1,A,CRITICAL,FAIL" in lines[1]
    assert "Screen Reader Lens" in lines[1]


def test_api_export_csv_endpoint(sample_audit_data):
    """Verify GET /v1/api/scans/{pid}/{sid}/export/csv endpoint."""
    with patch("app.routers.dashboard_api.get_scan_record", return_value=sample_audit_data):
        client = TestClient(app)
        res = client.get("/v1/api/scans/proj1/scan-999/export/csv", headers={"X-API-Key": "beacon_admin_key"})
        assert res.status_code == 200
        assert "text/csv" in res.headers.get("content-type", "")
        assert "attachment; filename=" in res.headers.get("content-disposition", "")
        assert "image-alt" in res.text


# ── §67: Report Generation Tests ──────────────────────────────────────────────

def test_report_generator_sections(sample_audit_data):
    """Verify multi-section report generation (§67)."""
    report = generate_enterprise_audit_report(sample_audit_data, profile_id="GLOBAL_WCAG_22_AA")

    assert "Executive Summary" in report["sections"]
    assert "Compliance & Legal Context" in report["sections"]
    assert "Persona Impact Analysis" in report["sections"]
    assert "Manual Review Queue" in report["sections"]
    assert "Remediation & Sandbox Status" in report["sections"]
    assert "Evidence Appendix" in report["sections"]

    # Invariant: Counts are accounted accurately
    assert report["counts"]["verified_violations"] == 1
    assert report["counts"]["needs_review"] == 1
    assert "coverage_caveat" in report["controlled_score"]


# ── §68: Accessibility Statement Tests ────────────────────────────────────────

def test_accessibility_statement_generator(sample_audit_data):
    """Verify accessibility statement draft follows W3C/PSBAR models without false claims (§68)."""
    statement = generate_accessibility_statement(
        sample_audit_data,
        organization_name="Acme Global",
        contact_email="a11y@acme.com",
    )

    # Invariant: Since issues remain, statement must NOT claim full compliance (§68)
    assert "partially compliant" in statement.lower()
    assert "fully compliant with" not in statement.lower()

    # Contains required standard sections
    assert "## 1. Compliance Status" in statement
    assert "## 2. Non-Accessible Content" in statement
    assert "## 5. Feedback and Contact Information" in statement
    assert "a11y@acme.com" in statement
    assert "does not constitute formal legal certification" in statement.lower()


# ── §69 & §70: Custom Profile Tests ───────────────────────────────────────────

def test_custom_profile_definition_and_labeling():
    """Verify custom profile system strictly labels custom rules as ORGANIZATION_RULE (§70)."""
    custom_rule = CustomRuleDefinition(
        rule_id="org-contrast-extra",
        name="Extra Contrast Standard 7:1",
        description="Internal branding guideline requiring 7:1 contrast for all buttons.",
        severity="moderate",
    )

    # Invariant: rule_type MUST be ORGANIZATION_RULE per §70
    assert custom_rule.to_dict()["rule_type"] == "ORGANIZATION_RULE"

    custom_prof = CustomProfileDefinition(
        profile_id="ACME_INTERNAL_A11Y",
        name="Acme Corporate Accessibility Standard",
        organization_id="org-acme",
        custom_rules=[custom_rule],
        required_criteria={"1.1.1", "1.4.3"},
        excluded_criteria={"1.2.4"},  # e.g. no live video on site
    )

    # Register in custom profile registry
    reg_res = custom_profile_registry.register_custom_profile(custom_prof)
    assert reg_res["status"] == "registered"
    assert reg_res["profile_id"] == "ACME_INTERNAL_A11Y"

    # Evaluate findings against custom profile
    findings = [
        {"id": "f-1", "wcag_criterion": "1.1.1", "description": "Alt missing", "rule_id": "image-alt"},
        {"id": "f-2", "wcag_criterion": "1.2.4", "description": "Live captions", "rule_id": "live-captions"},
    ]
    evaluation = evaluate_profile("ACME_INTERNAL_A11Y", findings)

    # 1.1.1 is mandatory; 1.2.4 was excluded so it shouldn't be a mandatory violation
    assert evaluation["mandatory_violations_count"] == 1
    assert evaluation["mandatory_violations"][0]["wcag_criterion"] == "1.1.1"
    assert "ORGANIZATION_RULE" in evaluation["disclaimer"]
