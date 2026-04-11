import json
from pathlib import Path

pass1 = json.loads(Path("evaluation/final_act_pass1.json").read_text(encoding="utf-8"))
pass2 = json.loads(Path("evaluation/final_act_pass2.json").read_text(encoding="utf-8"))
rule_metrics = json.loads(Path("evaluation/final_rule_level_metrics.json").read_text(encoding="utf-8"))
prod = json.loads(Path("evaluation/production_benchmark_results.json").read_text(encoding="utf-8"))

p1 = pass1.get("aggregate", {}).get("micro", {})
p2 = pass2.get("aggregate", {}).get("micro", {})

f1_1 = float(p1.get("f1") or 0.0)
f1_2 = float(p2.get("f1") or 0.0)
recall_1 = float(p1.get("recall") or 0.0)
recall_2 = float(p2.get("recall") or 0.0)
prec_1 = float(p1.get("precision") or 0.0)
prec_2 = float(p2.get("precision") or 0.0)

f1_drift = abs(f1_2 - f1_1)
recall_drift = abs(recall_2 - recall_1)
precision_drift = abs(prec_2 - prec_1)

rules = rule_metrics.get("rules") or rule_metrics.get("per_rule_metrics") or []
max_fp = max((int(r.get("fp", 0) or 0) for r in rules), default=0)

fast = prod.get("fast", []) if isinstance(prod, dict) else []
deep = prod.get("deep", []) if isinstance(prod, dict) else []
all_prod = [*fast, *deep]

warn_count = sum(1 for r in all_prod if bool((r.get("telemetry") or {}).get("suppression_warning", False)))
warn_rate = (warn_count / len(all_prod)) if all_prod else 0.0
structural_fp = sum(int(r.get("structural_fp", 0) or 0) for r in all_prod)

summary = prod.get("summary", {}) if isinstance(prod, dict) else {}
alignment_rate = float(((summary.get("overall") or {}).get("expectation_alignment_rate", 0.0)) or 0.0)

print("=== PHASE 11 SCORECARD ===")
print(f"ACT pass1 precision/recall/f1: {prec_1:.4f}/{recall_1:.4f}/{f1_1:.4f}")
print(f"ACT pass2 precision/recall/f1: {prec_2:.4f}/{recall_2:.4f}/{f1_2:.4f}")
print(f"Stability drift (precision/recall/f1): {precision_drift:.4f}/{recall_drift:.4f}/{f1_drift:.4f}")
print(f"Rule-level max FP count: {max_fp}")
print(f"Production suppression warnings: {warn_count}/{len(all_prod)} ({warn_rate:.1%})")
print(f"Production structural FP total: {structural_fp}")
print(f"Expectation alignment rate: {alignment_rate:.1%}")

print("--- Gates ---")
print(f"Gate ACT F1 >= 0.55: {'PASS' if f1_2 >= 0.55 else 'FAIL'}")
print(f"Gate ACT Recall >= 0.45: {'PASS' if recall_2 >= 0.45 else 'FAIL'}")
print(f"Gate ACT Precision >= 0.35: {'PASS' if prec_2 >= 0.35 else 'FAIL'}")
print(f"Gate Stability F1 drift <= 0.03: {'PASS' if f1_drift <= 0.03 else 'FAIL'}")
print(f"Gate Rule max FP == 0: {'PASS' if max_fp == 0 else 'FAIL'}")
print(f"Gate Suppression warning rate <= 0.10: {'PASS' if warn_rate <= 0.10 else 'FAIL'}")
print(f"Gate Structural FP total == 0: {'PASS' if structural_fp == 0 else 'FAIL'}")
print(f"Gate Expectation alignment >= 0.65: {'PASS' if alignment_rate >= 0.65 else 'FAIL'}")
