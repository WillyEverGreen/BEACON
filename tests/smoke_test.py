"""Smoke test for all 5 engine upgrades."""
from app.services.static_checks import StaticChecker
from app.services.confidence import apply_confidence_rules, _boost_cross_engine_agreement
from app.services.normalizer import AXE_WCAG_MAP, AXE_GROUPABLE_RULES, normalize_axe_results
from app.config import SCORING_CONFIG
from app.services.audit_runner import _calculate_score

HTML = "<html lang='en'><head><title>T</title></head><body></body></html>"
sc = StaticChecker(HTML, "http://test.com")
issues = sc.run_all()
print(f"StaticChecker: {len(issues)} issues on minimal page (expected 0-2)")

# Score with 300 ungrouped region violations — should be capped at 85
fake_issues = [
    {"rule_id": "region", "severity": "moderate", "confidence": 0.9, "is_grouped": False}
    for _ in range(300)
]
score = _calculate_score(fake_issues)
print(f"Score, 300 ungrouped region: {score} (expected ~85 — capped at max_per_rule=15)")

# Score with grouped region — counts as 1 finding weight
grouped_issues = [
    {"rule_id": "region", "severity": "moderate", "confidence": 0.9,
     "is_grouped": True, "evidence": {"affected_count": 300}}
]
score2 = _calculate_score(grouped_issues)
print(f"Score, 1 grouped region: {score2} (expected 98)")

# WCAG map coverage
print(f"WCAG map: {len(AXE_WCAG_MAP)} rules (expected 57)")
print(f"Groupable rules: {len(AXE_GROUPABLE_RULES)} (expected 13)")
assert "region" in AXE_GROUPABLE_RULES
assert "color-contrast" in AXE_WCAG_MAP
assert "duplicate-id" in AXE_WCAG_MAP

# normalize_axe_results grouping
fake_violation = [{
    "id": "region",
    "impact": "moderate",
    "description": "Ensures all page content is contained by landmarks",
    "help": "All page content should be contained by landmarks",
    "helpUrl": "https://dequeuniversity.com/rules/axe/4.10/region",
    "tags": ["cat.keyboard", "best-practice", "wcag2a", "wcag1311"],
    "nodes": [{"html": f"<div>El {i}</div>", "target": [f".el-{i}"], "failureSummary": "Fix"} for i in range(50)],
}]
normalized = normalize_axe_results(fake_violation, "http://test.com")
print(f"Axe normalization (50 region nodes): {len(normalized)} issues (expected 1 grouped)")
assert len(normalized) == 1
assert normalized[0].get("is_grouped") is True
assert normalized[0]["evidence"]["affected_count"] == 50

# Cross-engine confidence boost
test_issues = [
    {"rule_id": "missing-label", "confidence": 0.7, "confidence_tier": "medium", "confidence_sources": ["static"]},
    {"rule_id": "missing-label", "confidence": 0.9, "confidence_tier": "high", "confidence_sources": ["axe-core"]},
    {"rule_id": "button-name", "confidence": 0.6, "confidence_tier": "medium", "confidence_sources": ["static"]},
]
boosted = _boost_cross_engine_agreement(test_issues)
ml_issues = [i for i in boosted if i["rule_id"] == "missing-label"]
bn_issues = [i for i in boosted if i["rule_id"] == "button-name"]
print(f"Cross-engine boost: missing-label confidence={ml_issues[0]['confidence']} (expected >=0.92)")
print(f"Cross-engine boost: button-name confidence={bn_issues[0]['confidence']} (expected 0.6 — no boost)")
assert ml_issues[0]["confidence"] >= 0.92
assert bn_issues[0]["confidence"] == 0.6

# Color contrast checker
html_contrast = """
<html lang='en'><head><title>T</title></head>
<body>
  <p style='color: rgb(200,200,200); background-color: rgb(255,255,255);'>Light gray on white — bad contrast</p>
  <p style='color: rgb(0,0,0); background-color: rgb(255,255,255);'>Black on white — good contrast</p>
</body></html>
"""
sc2 = StaticChecker(html_contrast, "http://test.com")
contrast_issues = sc2.check_color_contrast()
print(f"Color contrast: {len(contrast_issues)} issues (expected 1, light gray fails)")
assert len(contrast_issues) == 1
assert "1.4.3" in contrast_issues[0]["wcag_criterion"]

# Duplicate ID checker
html_dup = "<html><head><title>T</title></head><body><div id='nav'>A</div><div id='nav'>B</div></body></html>"
sc3 = StaticChecker(html_dup, "http://test.com")
dup_issues = sc3.check_duplicate_ids()
print(f"Duplicate IDs: {len(dup_issues)} issues (expected 1)")
assert len(dup_issues) == 1
assert dup_issues[0]["rule_id"] == "duplicate-id"

print("\nAll smoke tests PASSED!")
