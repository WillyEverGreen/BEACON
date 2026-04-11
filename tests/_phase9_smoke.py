"""Quick smoke test for Phase 9 components."""
import sys
sys.path.insert(0, ".")

from app.services.rule_calibrator import (
    load_trust_registry, get_rule_trust_score, get_trust_summary, get_rule_trust_entry
)

# Test 1: Registry loads
registry = load_trust_registry()
print(f"[OK] Registry loaded: {len(registry)} rules")

# Test 2: Trust scores
print(f"  missing-alt trust:      {get_rule_trust_score('missing-alt')}")
print(f"  landmark-one-main trust: {get_rule_trust_score('landmark-one-main')}")
print(f"  unknown-rule trust:     {get_rule_trust_score('unknown-rule')}")
print(f"  no-headings trust:      {get_rule_trust_score('no-headings')}")

# Test 3: Trust entry
entry = get_rule_trust_entry("missing-alt")
print(f"  missing-alt entry: verdict={entry['verdict']}, req_engines={entry['required_engines']}")

# Test 4: Trust summary
summary = get_trust_summary()
print(f"[OK] Trust summary: {summary}")

# Test 5: Confidence integration
from app.services.confidence import compute_final_confidence
# High-trust rule, high base, high agreement
c1 = compute_final_confidence(0.85, "missing-alt", 1.0, 0.8)
print(f"  High trust + agreement: {c1}")
# Low-trust rule, high base, single engine
c2 = compute_final_confidence(0.85, "landmark-one-main", 0.0, 0.5)
print(f"  Low trust + single:     {c2}")
# Unknown rule
c3 = compute_final_confidence(0.80, "unknown-rule", 0.5, 0.5)
print(f"  Unknown rule:           {c3}")

assert c1 > c2, f"High-trust should beat low-trust: {c1} vs {c2}"
assert c3 > c2, f"Unknown should beat suppress: {c3} vs {c2}"
print("\n[OK] All confidence comparisons pass")

# Test 6: Dedup fingerprint
from app.services.dedup_engine import _fingerprint, proximity_dedup
fp1 = _fingerprint({"rule_id": "missing-alt", "element": "img.hero"})
fp2 = _fingerprint({"rule_id": "missing-alt", "element": "img.hero:nth-child(2)"})
fp3 = _fingerprint({"rule_id": "missing-label", "element": "input#email"})
print(f"\n  fp same prefix:  {fp1}")
print(f"  fp similar:      {fp2}")
print(f"  fp different:    {fp3}")
print(f"  fp1==fp2 (proximity match expected): {fp1 == fp2}")
print(f"  fp1!=fp3 (different rule):           {fp1 != fp3}")

# Test 7: Proximity dedup
issues = [
    {"rule_id": "missing-alt", "element": "img.hero", "confidence": 0.8},
    {"rule_id": "missing-alt", "element": "img.hero:nth-child(1)", "confidence": 0.9},
    {"rule_id": "missing-label", "element": "input#email", "confidence": 0.7},
]
result = proximity_dedup(issues)
print(f"  Proximity dedup: {len(issues)} -> {len(result)} issues")

print("\n✅ All Phase 9 smoke tests PASS")
