"""Unit tests for Phase 4 Multi-Engine Consensus & ACT Adjudication."""

import pytest
from app.audit.adapters.axe_adapter import AxeAdapter
from app.audit.adapters.ibm_adapter import IBMAdapter
from app.audit.adapters.alfa_adapter import AlfaAdapter
from app.audit.adapters.heuristics_adapter import HeuristicsAdapter
from app.audit.consensus import ConsensusEngine
from app.models.contracts import Finding


def test_ibm_adapter_normalization():
    adapter = IBMAdapter()
    raw_issue = {
        "ruleId": "image_alt_exists",
        "value": "violation",
        "path": {"dom": "div.banner > img"},
        "snippet": "<img src='hero.png'>",
        "message": "Images must have an alt attribute or aria-label",
        "toolkit": {"num": "1.1.1"},
        "category": "Accessibility",
        "reasonId": "no_alt",
    }
    finding = adapter.normalize(raw_issue)
    assert finding.engine == "ibm_equal_access"
    assert finding.rule_id == "image_alt_exists"
    assert finding.wcag_criterion == "1.1.1"
    assert finding.severity == "serious"
    assert finding.selector == "div.banner > img"
    assert finding.confidence == 0.88
    assert finding.evidence["reason_id"] == "no_alt"


def test_alfa_adapter_normalization():
    adapter = AlfaAdapter()
    raw_issue = {
        "rule": "sia-r1",
        "outcome": "failed",
        "target": "div.banner > img",
        "html": "<img src='hero.png'>",
        "message": "The <img> element has no alt attribute",
    }
    finding = adapter.normalize(raw_issue)
    assert finding.engine == "alfa"
    assert finding.rule_id == "sia-r1"
    assert finding.wcag_criterion == "1.1.1"
    assert finding.act_rule_id == "23a2a8"
    assert finding.act_adjudicated is True
    assert finding.confidence == 0.95


def test_consensus_engine_multi_engine_agreement():
    axe_adapter = AxeAdapter()
    ibm_adapter = IBMAdapter()
    alfa_adapter = AlfaAdapter()

    # 3 engines detecting the same missing alt on the same element
    axe_issue = {
        "id": "image-alt",
        "impact": "critical",
        "tags": ["cat.text-alternatives", "wcag2a", "wcag111", "ACT-23a2a8"],
        "description": "Ensures <img> elements have alternate text",
        "help": "Images must have alternate text",
        "nodes": [
            {
                "any": [], "all": [], "none": [],
                "impact": "critical",
                "html": "<img src='banner.png' class='hero'>",
                "target": ["img.hero"],
                "failureSummary": "Element does not have an alt attribute",
            }
        ],
    }
    ibm_issue = {
        "ruleId": "img_alt_valid",
        "value": "violation",
        "path": {"dom": "img.hero"},
        "snippet": "<img src='banner.png' class='hero'>",
        "message": "Image requires valid alternative text",
        "toolkit": {"num": "1.1.1"},
    }
    alfa_issue = {
        "rule": "sia-r1",
        "outcome": "failed",
        "target": "img.hero",
        "html": "<img src='banner.png' class='hero'>",
    }

    f_axe = axe_adapter.normalize(axe_issue)
    f_ibm = ibm_adapter.normalize(ibm_issue)
    f_alfa = alfa_adapter.normalize(alfa_issue)

    consensus_engine = ConsensusEngine()
    results = consensus_engine.reconcile([f_axe, f_ibm, f_alfa])

    assert len(results) == 1
    reconciled = results[0]

    assert reconciled.agreement_count == 3
    assert set(reconciled.participating_engines) == {"axe", "ibm_equal_access", "alfa"}
    assert reconciled.wcag_criterion == "1.1.1"
    assert reconciled.severity == "critical"  # axe marked critical
    assert reconciled.act_rule_id in ("ACT-23a2a8", "23a2a8")
    assert reconciled.act_adjudicated is True
    # Calibrated confidence should be very high (>= 0.95)
    assert reconciled.confidence >= 0.95
    assert "axe" in reconciled.evidence
    assert "ibm_equal_access" in reconciled.evidence
    assert "alfa" in reconciled.evidence


def test_consensus_engine_disagreement_and_filtering():
    consensus_engine = ConsensusEngine(min_confidence=0.60)

    # A low-confidence unconfirmed single-engine heuristic
    weak_finding = Finding(
        id="weak-1",
        rule_id="beacon-guess",
        engine="beacon_heuristics",
        engine_version="2.1.0",
        rule_version="2.1.0",
        beacon_version="2.1.0",
        wcag_criterion="1.3.1",
        wcag_level="A",
        severity="minor",
        selector="div.unknown",
        selector_fingerprint="fp-div-unknown",
        html_snippet="<div></div>",
        message="Possible issue",
        confidence=0.45,
    )

    # Strong single-engine finding
    strong_finding = Finding(
        id="strong-1",
        rule_id="color-contrast",
        engine="axe",
        engine_version="4.10.2",
        rule_version="4.10.2",
        beacon_version="2.1.0",
        wcag_criterion="1.4.3",
        wcag_level="AA",
        severity="serious",
        selector="p.subtext",
        selector_fingerprint="fp-p-subtext",
        html_snippet="<p class='subtext'>Low contrast</p>",
        message="Insufficient contrast",
        confidence=0.88,
    )

    results = consensus_engine.reconcile([weak_finding, strong_finding])

    # weak_finding (0.45) is filtered out by min_confidence=0.60
    assert len(results) == 1
    assert results[0].id == "strong-1"
    assert results[0].confidence == 0.88
