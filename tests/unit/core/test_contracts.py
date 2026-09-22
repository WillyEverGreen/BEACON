"""Unit tests for Phase 0 Core Contracts and Normalized Finding Schema."""

import pytest

from app.models.contracts import (
    Finding,
    Fingerprint,
    PatchResult,
)


def test_fingerprint_immutability_and_signature():
    fp = Fingerprint(
        dom_hash="a1b2c3d4e5f67890",
        landmarks=("header", "main", "footer"),
        roles=("navigation", "banner"),
        interactive_counts={"button": 5, "link": 12},
        form_count=1,
        text_density_ratio=0.45,
    )

    sig = fp.signature()
    assert "a1b2c3d4e5f6" in sig
    assert "LM:footer,header,main" in sig
    assert "ROLES:banner,navigation" in sig
    assert "ACT:17" in sig
    assert "FORMS:1" in sig

    # Frozen / immutable check
    with pytest.raises(AttributeError):
        fp.dom_hash = "new_hash"  # type: ignore[misc]


def test_finding_creation_and_serialization():
    finding = Finding(
        id="f-001",
        rule_id="color-contrast",
        engine="axe",
        engine_version="4.10.2",
        rule_version="1.0.0",
        beacon_version="2.1.0",
        wcag_criterion="1.4.3",
        wcag_level="AA",
        severity="serious",
        selector="button.primary",
        selector_fingerprint="button[class=primary]",
        html_snippet="<button class='primary'>Submit</button>",
        message="Element has insufficient color contrast",
        evidence={"contrast_ratio": 2.5, "required_ratio": 4.5},
        confidence=0.92,
        agreement_count=2,
        participating_engines=["axe", "beacon_heuristics"],
    )

    data = finding.to_dict()
    assert data["id"] == "f-001"
    assert data["rule_id"] == "color-contrast"
    assert data["engine"] == "axe"
    assert data["engine_version"] == "4.10.2"
    assert data["confidence"] == 0.92
    assert "beacon_heuristics" in data["participating_engines"]
    assert data["timestamp"] != ""


def test_patch_result_contract():
    res = PatchResult(
        finding_id="f-001",
        original_html="<img src='logo.png'>",
        patched_html="<img src='logo.png' alt='Company Logo'>",
        patch_accepted=True,
        violations_before_count=1,
        violations_after_count=0,
        new_violations_introduced=0,
        syntax_valid=True,
        execution_time_ms=12.4,
    )

    assert res.patch_accepted is True
    assert res.new_violations_introduced == 0
    assert res.syntax_valid is True
