"""
Unit tests for Batch 5: Regulatory Control Profiles & Persona Lenses (§25–§38).
"""

import copy

from app.profiles.engine import (
    attach_persona_lenses_to_findings,
    evaluate_profile,
    map_finding_to_persona_lenses,
    resolve_profiles_for_scan,
)
from app.profiles.models import PersonaLens, RegulatoryProfile
from app.profiles.registry import (
    PERSONA_LENSES,
    REGULATORY_PROFILES,
)


def test_regulatory_profiles_registry_completeness():
    """Verify that all standard regulatory profiles exist with required metadata (§25-§30)."""
    expected_keys = [
        "GLOBAL_WCAG_22_AA",
        "US_SECTION_508",
        "UK_PUBLIC_SECTOR",
        "EU_EN_301_549",
        "INDIA_GIGW_3",
    ]
    for key in expected_keys:
        assert key in REGULATORY_PROFILES
        p = REGULATORY_PROFILES[key]
        assert isinstance(p, RegulatoryProfile)
        assert p.profile_id == key
        assert len(p.name) > 0
        assert len(p.jurisdiction) > 0
        assert len(p.technical_standard) > 0
        assert len(p.mandatory_criteria) > 0
        assert "legal" in p.disclaimer.lower()

        # Non-global profiles must have verification source metadata
        if key != "GLOBAL_WCAG_22_AA":
            assert p.verification_source is not None
            assert "authority" in p.verification_source
            assert "standard" in p.verification_source


def test_persona_lenses_registry_completeness():
    """Verify that all 5 persona lenses exist with descriptive templates (§32-§38)."""
    expected_lenses = [
        "SCREEN_READER",
        "KEYBOARD_MOTOR",
        "LOW_VISION",
        "COGNITIVE",
        "DEAF_HARD_OF_HEARING",
    ]
    for lid in expected_lenses:
        assert lid in PERSONA_LENSES
        lens = PERSONA_LENSES[lid]
        assert isinstance(lens, PersonaLens)
        assert lens.id == lid
        assert len(lens.relevant_criteria) > 0
        assert len(lens.user_impact_template) > 10


def test_evaluate_profile_and_non_mutation():
    """Verify profile evaluation correctly categorizes violations without mutating raw findings (§31)."""
    findings = [
        {
            "id": "f-1",
            "rule_id": "image-alt",
            "wcag_criterion": "1.1.1",
            "description": "Image missing alt text",
            "impact": "serious",
        },
        {
            "id": "f-2",
            "rule_id": "target-size",
            "wcag_criterion": "2.5.8",
            "description": "Touch target under 24px",
            "impact": "moderate",
        },
    ]

    original_findings = copy.deepcopy(findings)

    # Evaluate against US Section 508 (where 1.1.1 is mandatory, 2.5.8 is advisory)
    res_508 = evaluate_profile("US_SECTION_508", findings)
    assert res_508["profile_id"] == "US_SECTION_508"
    assert res_508["status"] == "NON_CONFORMANT"
    assert res_508["mandatory_violations_count"] == 1
    assert res_508["advisory_findings_count"] == 1
    assert res_508["mandatory_violations"][0]["wcag_criterion"] == "1.1.1"
    assert "Section 508" in res_508["mandatory_violations"][0]["regulatory_clause"]
    assert res_508["advisory_findings"][0]["wcag_criterion"] == "2.5.8"

    # Evaluate against Global WCAG 2.2 AA (where both 1.1.1 and 2.5.8 are mandatory)
    res_wcag = evaluate_profile("GLOBAL_WCAG_22_AA", findings)
    assert res_wcag["profile_id"] == "GLOBAL_WCAG_22_AA"
    assert res_wcag["mandatory_violations_count"] == 2
    assert res_wcag["advisory_findings_count"] == 0

    # Invariant: Original findings list must NOT have been mutated
    assert findings == original_findings


def test_resolve_profiles_for_scan_multi_lens():
    """Verify multi-profile resolution for a single scan execution (§31)."""
    findings = [
        {
            "id": "f-1",
            "rule_id": "color-contrast",
            "wcag_criterion": "1.4.3",
            "description": "Insufficient contrast",
        }
    ]

    result = resolve_profiles_for_scan(
        findings,
        requested_profile_ids=["GLOBAL_WCAG_22_AA", "US_SECTION_508", "EU_EN_301_549", "INDIA_GIGW_3"],
    )

    assert len(result["evaluated_profiles"]) == 4
    for pid in ["GLOBAL_WCAG_22_AA", "US_SECTION_508", "EU_EN_301_549", "INDIA_GIGW_3"]:
        assert pid in result["profile_evaluations"]
        assert result["summary"][pid]["mandatory_violations"] == 1
        assert result["summary"][pid]["status"] == "NON_CONFORMANT"


def test_map_finding_to_persona_lenses():
    """Verify that findings are accurately mapped to relevant persona lenses with explanations (§32-§38)."""
    # 1. Screen Reader finding
    sr_finding = {
        "wcag_criterion": "1.1.1",
        "rule_id": "image-alt",
        "description": "Image is missing an alternative text description.",
    }
    lenses = map_finding_to_persona_lenses(sr_finding)
    lens_ids = [l["id"] for l in lenses]
    assert "SCREEN_READER" in lens_ids
    sr_entry = next(l for l in lenses if l["id"] == "SCREEN_READER")
    assert sr_entry["relevance"] >= 0.9
    assert "screen reader" in sr_entry["user_impact_explanation"].lower()

    # 2. Keyboard / Motor finding
    kb_finding = {
        "wcag_criterion": "2.1.1",
        "rule_id": "keyboard-trap",
        "description": "Focus trapped in modal dialog.",
    }
    lenses_kb = map_finding_to_persona_lenses(kb_finding)
    kb_ids = [l["id"] for l in lenses_kb]
    assert "KEYBOARD_MOTOR" in kb_ids

    # 3. Low Vision finding
    lv_finding = {
        "wcag_criterion": "1.4.3",
        "rule_id": "color-contrast",
        "description": "Low contrast ratio 2.5:1 on body text.",
    }
    lenses_lv = map_finding_to_persona_lenses(lv_finding)
    lv_ids = [l["id"] for l in lenses_lv]
    assert "LOW_VISION" in lv_ids

    # 4. Cognitive finding
    cog_finding = {
        "wcag_criterion": "3.3.8",
        "rule_id": "accessible-auth",
        "description": "Password input blocks paste.",
    }
    lenses_cog = map_finding_to_persona_lenses(cog_finding)
    cog_ids = [l["id"] for l in lenses_cog]
    assert "COGNITIVE" in cog_ids

    # 5. Deaf / Hard of Hearing finding
    dhh_finding = {
        "wcag_criterion": "1.2.2",
        "rule_id": "video-captions",
        "description": "Video player lacks closed captions.",
    }
    lenses_dhh = map_finding_to_persona_lenses(dhh_finding)
    dhh_ids = [l["id"] for l in lenses_dhh]
    assert "DEAF_HARD_OF_HEARING" in dhh_ids


def test_attach_persona_lenses_to_findings():
    """Verify batch attachment of persona lenses to a findings list."""
    findings = [
        {"id": "1", "wcag_criterion": "1.1.1", "rule_id": "image-alt"},
        {"id": "2", "wcag_criterion": "2.1.1", "rule_id": "keyboard"},
    ]
    enriched = attach_persona_lenses_to_findings(findings)
    assert len(enriched) == 2
    assert "persona_lenses" in enriched[0]
    assert "persona_lenses" in enriched[1]
    assert len(enriched[0]["persona_lenses"]) > 0
    assert len(enriched[1]["persona_lenses"]) > 0
