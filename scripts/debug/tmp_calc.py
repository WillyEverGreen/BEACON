"""Quick math: what would precision/recall be after fixing no-headings FP?"""
import json

d = json.load(open('evaluation/benchmark_results.json'))
cases = d['cases']

# Current: TP=7, FP=13, FN=13
# If we remove all no-headings FP (12 cases) → FP drops by 12
# But we also stop reporting no-headings, so we might lose some TP too
# Let's calculate precisely

# Count by rule
fp_by_rule = {}
fn_by_rule = {}
tp_rules = set()
for c in cases:
    for r in c.get('unexpected_rule_ids', []):
        fp_by_rule[r] = fp_by_rule.get(r, 0) + 1
    for r in c.get('missing_rule_ids', []):
        fn_by_rule[r] = fn_by_rule.get(r, 0) + 1

print("FP by rule:", fp_by_rule)
print("FN by rule:", fn_by_rule)

# After removing no-headings from output (structural suppression):
# FP: 13 - 12 (no-headings) = 1 (aria-required-parent)
# FN: 13 stays the same (we can't detect focus-management or semantic-html)
# TP: stays 7 (no-headings was never a TP)

new_tp = 7
new_fp = 13 - fp_by_rule.get('no-headings', 0) 
new_fn = 13  # unchanged

new_precision = new_tp / (new_tp + new_fp) if (new_tp + new_fp) else 0
new_recall = new_tp / (new_tp + new_fn) if (new_tp + new_fn) else 0
new_f1 = 2 * new_precision * new_recall / (new_precision + new_recall) if (new_precision + new_recall) else 0

print(f"\nProjected after no-headings suppression:")
print(f"TP={new_tp}, FP={new_fp}, FN={new_fn}")
print(f"Precision: {new_precision:.1%}")
print(f"Recall: {new_recall:.1%}")
print(f"F1: {new_f1:.1%}")
print(f"\nTarget: Precision ≥45%, Recall ≥50%")
print(f"Precision {'PASS' if new_precision >= 0.45 else 'FAIL'}, Recall {'PASS' if new_recall >= 0.50 else 'FAIL'}")
