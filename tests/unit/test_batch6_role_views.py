"""
Unit tests for Batch 6: Role Views, Controlled Scoring, Multi-Lens Projections & APIs (§39–§48).
"""

import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.role_views import (
    SUPPORTED_ROLES,
    build_compliance_view,
    build_developer_view,
    build_evidence_first_finding,
    build_executive_view,
    build_qa_specialist_view,
    build_role_view,
    calculate_controlled_score,
    calculate_profile_score,
    project_scan_view,
)


@pytest.fixture
def sample_findings():
    return [
        {
            "id": "f-001",
            "rule_id": "image-alt",
            "wcag_criterion": "1.1.1",
            "wcag_level": "A",
            "severity": "critical",
            "confidence": 0.95,
            "verdict": "fail",
            "selector": "img#hero",
            "html": '<img id="hero" src="hero.jpg">',
            "file": "components/Hero.tsx",
            "line": 42,
            "suggested_fix": '<img id="hero" src="hero.jpg" alt="Company mascot welcoming users">',
            "description": "Image missing required alternative text.",
        },
        {
            "id": "f-002",
            "rule_id": "target-size",
            "wcag_criterion": "2.5.8",
            "wcag_level": "AA",
            "severity": "moderate",
            "confidence": 0.88,
            "verdict": "fail",
            "selector": "button.icon-btn",
            "html": '<button class="icon-btn">X</button>',
            "file": "components/Header.tsx",
            "line": 15,
            "suggested_fix": '<button class="icon-btn" style="min-width: 24px; min-height: 24px;">X</button>',
            "description": "Touch target size is under 24x24 CSS pixels.",
        },
        {
            "id": "f-003",
            "rule_id": "color-contrast",
            "wcag_criterion": "1.4.3",
            "wcag_level": "AA",
            "severity": "serious",
            "confidence": 0.65,
            "verdict": "needs_review",
            "selector": "span.tag",
            "html": '<span class="tag">Active</span>',
            "description": "Text rendered over dynamic background image; contrast needs verification.",
        },
        {
            "id": "f-004",
            "rule_id": "button-name",
            "wcag_criterion": "4.1.2",
            "wcag_level": "A",
            "severity": "critical",
            "confidence": 0.98,
            "verdict": "pass",
            "selector": "button#submit",
            "html": '<button id="submit">Submit</button>',
            "description": "Button has accessible name.",
        },
    ]


# ── §48: Evidence-First Finding Contract Tests ────────────────────────────────

def test_evidence_first_finding_contract(sample_findings):
    """Verify that finding is transformed to canonical evidence-first contract (§48)."""
    raw = sample_findings[0]
    contract = build_evidence_first_finding(raw)

    assert contract["finding_id"] == "f-001"
    assert contract["rule_id"] == "image-alt"
    assert contract["wcag"]["criterion"] == "1.1.1"
    assert contract["wcag"]["level"] == "A"
    assert contract["verification"]["verdict"] == "fail"
    assert contract["verification"]["confidence"] == 0.95
    assert contract["location"]["selector"] == "img#hero"
    assert contract["location"]["file"] == "components/Hero.tsx"
    assert contract["remediation"]["fix"] == raw["suggested_fix"]
    assert "SCREEN_READER" in [p["id"] for p in contract["personas"]]
    assert isinstance(contract["profiles"], dict)
    assert len(contract["profiles"]) > 0


# ── §44: Controlled Score Model Tests ─────────────────────────────────────────

def test_controlled_score_model(sample_findings):
    """Verify mathematical properties of controlled score model (§44)."""
    # 1. Zero scorable violations -> 100.0 score
    perfect = calculate_controlled_score([])
    assert perfect["score"] == 100.0
    assert perfect["criteria_pass_rate"] == 100.0
    assert perfect["total_penalty_applied"] == 0.0

    # 2. PASS finding should NEVER penalize the score
    pass_finding = [sample_findings[3]]  # verdict == "pass"
    pass_res = calculate_controlled_score(pass_finding)
    assert pass_res["score"] == 100.0
    assert pass_res["total_penalty_applied"] == 0.0

    # 3. Penalties applied only for FAIL/NEEDS_REVIEW
    score_res = calculate_controlled_score(sample_findings)
    assert score_res["score"] < 100.0
    assert score_res["total_penalty_applied"] > 0
    assert "critical" in score_res["penalties_by_severity"]
    assert "coverage_caveat" in score_res
    assert "mathematically impossible" in score_res["coverage_caveat"]


# ── §45: Profile-Specific Scoring Tests ───────────────────────────────────────

def test_profile_specific_score(sample_findings):
    """Verify that profile-specific score respects jurisdiction criteria (§45)."""
    # In US Section 508, 1.1.1 is mandatory, 2.5.8 is advisory
    sec508_score = calculate_profile_score(sample_findings, profile_id="US_SECTION_508")
    assert sec508_score["profile_id"] == "US_SECTION_508"
    assert sec508_score["mandatory_violations_count"] == 1  # 1.1.1 is mandatory
    assert sec508_score["advisory_findings_count"] >= 1     # 2.5.8 is advisory
    assert "Section 508" in sec508_score["technical_standard"]

    # In Global WCAG 2.2 AA, both 1.1.1 and 2.5.8 are mandatory
    wcag_score = calculate_profile_score(sample_findings, profile_id="GLOBAL_WCAG_22_AA")
    assert wcag_score["profile_id"] == "GLOBAL_WCAG_22_AA"
    assert wcag_score["mandatory_violations_count"] >= 2


# ── §39–§43: Role-Specific Views Tests ────────────────────────────────────────

def test_developer_view(sample_findings):
    """Verify Developer View focuses on code, selectors, and fixes (§40)."""
    dev_view = build_developer_view(sample_findings)
    assert dev_view["role"] == "DEVELOPER"
    assert dev_view["total_actionable_findings"] == 4
    assert "copy_fix" in dev_view["supported_actions"]
    assert "components/Hero.tsx" in dev_view["by_component"]
    first = dev_view["findings"][0]
    assert "selector" in first
    assert "suggested_fix" in first
    assert "file" in first


def test_qa_specialist_view(sample_findings):
    """Verify QA Specialist View prioritizes review queue and reproduction steps (§41)."""
    qa_view = build_qa_specialist_view(sample_findings)
    assert qa_view["role"] == "QA_A11Y"
    assert qa_view["needs_review_count"] == 1  # f-003 has verdict needs_review
    assert len(qa_view["review_queue"]) == 1
    review_item = qa_view["review_queue"][0]
    assert review_item["finding_id"] == "f-003"
    assert "reproduction_steps" in review_item
    assert "confirm_finding" in qa_view["supported_actions"]


def test_compliance_view(sample_findings):
    """Verify Compliance View reports regulatory conformance and legal disclaimer (§42)."""
    comp_view = build_compliance_view(sample_findings, profile_id="GLOBAL_WCAG_22_AA")
    assert comp_view["role"] == "COMPLIANCE"
    assert comp_view["technical_conformance_status"] in {"NON_CONFORMANT", "CONFORMANT_WITH_ADVISORY", "CONFORMANT"}
    assert "disclaimer" in comp_view
    assert "legal" in comp_view["disclaimer"].lower()
    assert len(comp_view["unassessed_mandatory_criteria"]) > 0


def test_executive_view(sample_findings):
    """Verify Executive View summarizes risk, affected personas, and high-impact issues (§43)."""
    exec_view = build_executive_view(sample_findings, pages_scanned=5, templates_count=3)
    assert exec_view["role"] == "EXECUTIVE"
    assert exec_view["pages_assessed"] == 5
    assert exec_view["templates_affected"] == 3
    assert exec_view["critical_and_serious_issues"] == 2  # f-001 (critical) + f-003 (serious)
    assert "affected_personas_summary" in exec_view
    assert "SCREEN_READER" in exec_view["affected_personas_summary"]
    assert "executive_summary_statement" in exec_view


def test_build_role_view_dispatcher(sample_findings):
    """Verify build_role_view correctly dispatches to all supported roles."""
    for role in SUPPORTED_ROLES:
        res = build_role_view(sample_findings, role=role)
        assert res["role"] == role

    with pytest.raises(ValueError):
        build_role_view(sample_findings, role="INVALID_ROLE")


# ── §46 & §47: One Scan Many Lenses Projection Tests ─────────────────────────

def test_project_scan_view_multi_lens(sample_findings):
    """Verify projection of a single scan across multiple lenses without mutating evidence (§47)."""
    scan_data = {
        "scan_id": "scan-12345",
        "url": "https://example.com",
        "issues": sample_findings,
        "pages_scanned": 3,
    }
    orig_scan = copy.deepcopy(scan_data)

    # 1. Project as Developer under US Section 508
    dev_proj = project_scan_view(scan_data, profile_id="US_SECTION_508", view="DEVELOPER")
    assert dev_proj["applied_lenses"]["profile"] == "US_SECTION_508"
    assert dev_proj["applied_lenses"]["role_view"] == "DEVELOPER"
    assert dev_proj["view_data"]["role"] == "DEVELOPER"

    # 2. Project as Compliance under UK Public Sector
    comp_proj = project_scan_view(scan_data, profile_id="UK_PUBLIC_SECTOR", view="COMPLIANCE")
    assert comp_proj["applied_lenses"]["profile"] == "UK_PUBLIC_SECTOR"
    assert comp_proj["applied_lenses"]["role_view"] == "COMPLIANCE"

    # 3. Project with Persona Filter (SCREEN_READER)
    sr_proj = project_scan_view(scan_data, persona_id="SCREEN_READER", view="DEVELOPER")
    assert sr_proj["applied_lenses"]["persona"] == "SCREEN_READER"

    # 4. Invariant: Original scan data is completely unmutated
    assert scan_data == orig_scan


# ── §46: API Integration Tests ────────────────────────────────────────────────

def test_api_profiles_and_personas_endpoints():
    """Verify GET /api/profiles and GET /api/personas endpoints."""
    client = TestClient(app)
    headers = {"X-API-Key": "beacon_admin_key"}

    res_prof = client.get("/v1/api/profiles", headers=headers)
    assert res_prof.status_code == 200
    profiles = res_prof.json()
    assert isinstance(profiles, list)
    assert any(p["profile_id"] == "GLOBAL_WCAG_22_AA" for p in profiles)
    assert any(p["profile_id"] == "US_SECTION_508" for p in profiles)

    res_pers = client.get("/v1/api/personas", headers=headers)
    assert res_pers.status_code == 200
    personas = res_pers.json()
    assert isinstance(personas, list)
    assert any(p["id"] == "SCREEN_READER" for p in personas)
    assert any(p["id"] == "KEYBOARD_MOTOR" for p in personas)


def test_api_project_audit_view_endpoint(sample_findings):
    """Verify POST /audit/view endpoint computes projection on demand (§46)."""
    client = TestClient(app)
    headers = {"X-API-Key": "beacon_admin_key"}

    payload = {
        "id": "audit-abc",
        "url": "https://example.com",
        "issues": sample_findings,
    }

    res = client.post(
        "/v1/audit/view?profile=US_SECTION_508&view=DEVELOPER",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["applied_lenses"]["profile"] == "US_SECTION_508"
    assert data["applied_lenses"]["role_view"] == "DEVELOPER"
    assert data["view_data"]["role"] == "DEVELOPER"
    assert len(data["view_data"]["findings"]) > 0

