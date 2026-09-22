"""Unit tests for Phase 7 Enterprise Output Layer: SARIF 2.1.0 & W3C EARL 1.0."""

import pytest

from app.audit.exporters import export_to_earl, export_to_sarif
from app.models.contracts import Finding


@pytest.fixture
def sample_findings():
    f1 = Finding(
        id="finding-1",
        rule_id="image-alt",
        engine="axe",
        engine_version="4.10.2",
        rule_version="4.10.2",
        beacon_version="2.1.0",
        wcag_criterion="1.1.1",
        wcag_level="A",
        severity="critical",
        selector="img.hero",
        selector_fingerprint="fp-img-hero",
        html_snippet="<img src='hero.png' class='hero'>",
        message="Image missing required alt attribute",
        confidence=0.96,
        agreement_count=2,
        participating_engines=["axe", "alfa"],
        act_rule_id="23a2a8",
        act_adjudicated=True,
    )
    f2 = Finding(
        id="finding-2",
        rule_id="heading-order",
        engine="beacon_heuristics",
        engine_version="2.1.0",
        rule_version="2.1.0",
        beacon_version="2.1.0",
        wcag_criterion="1.3.1",
        wcag_level="A",
        severity="moderate",
        selector="main > h3.subtitle",
        selector_fingerprint="fp-main-h3",
        html_snippet="<h3 class='subtitle'>Jumped</h3>",
        message="Heading hierarchy skipped from h1 to h3",
        confidence=0.85,
        agreement_count=1,
        participating_engines=["beacon_heuristics"],
    )
    return [f1, f2]


def test_export_to_sarif(sample_findings):
    sarif = export_to_sarif(sample_findings, target_url="https://example.com/home")

    assert sarif["version"] == "2.1.0"
    assert "https://raw.githubusercontent.com/oasis-tcs/sarif-spec" in sarif["$schema"]
    runs = sarif["runs"]
    assert len(runs) == 1

    driver = runs[0]["tool"]["driver"]
    assert driver["name"] == "BEACON"
    assert len(driver["rules"]) == 2

    results = runs[0]["results"]
    assert len(results) == 2

    # Verify severity mapping: critical -> error, moderate -> warning
    levels = {r["ruleId"]: r["level"] for r in results}
    assert levels["image-alt"] == "error"
    assert levels["heading-order"] == "warning"

    # Verify locations and properties
    res1 = next(r for r in results if r["ruleId"] == "image-alt")
    assert res1["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "https://example.com/home"
    assert res1["locations"][0]["logicalLocations"][0]["name"] == "img.hero"
    assert res1["properties"]["act_adjudicated"] is True
    assert res1["properties"]["confidence"] == 0.96


def test_export_to_earl(sample_findings):
    earl = export_to_earl(sample_findings, target_url="https://example.com/home")

    assert "@context" in earl
    assert earl["@context"]["earl"] == "http://www.w3.org/ns/earl#"

    graph = earl["@graph"]
    # 1 Assertor + 1 TestSubject + 2 Assertions = 4 items
    assert len(graph) == 4

    types_in_graph = [item.get("@type") for item in graph]
    assert any("Assertor" in t for t in types_in_graph if isinstance(t, list))
    assert any("TestSubject" in t for t in types_in_graph if isinstance(t, list))

    assertions = [item for item in graph if item.get("@type") == "Assertion"]
    assert len(assertions) == 2

    a1 = assertions[0]
    assert a1["subject"] == "https://example.com/home"
    assert a1["result"]["outcome"] == "earl:failed"
    assert a1["result"]["pointer"]["ptr:expression"] == "img.hero"
    assert a1["result"]["earl:info"]["confidence"] == 0.96
