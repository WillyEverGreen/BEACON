"""
Seed the rule_trust_registry.json from ACT benchmark results.
Run once: python app/data/_seed_trust_registry.py
"""
import json
from collections import Counter
from pathlib import Path

ACT_RESULTS = Path("evaluation/retest_act_latest.json")
OUTPUT = Path("app/data/rule_trust_registry.json")


def main():
    with ACT_RESULTS.open("r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("cases", [])
    rule_tp: Counter = Counter()
    rule_fp: Counter = Counter()
    rule_fn: Counter = Counter()

    for case in cases:
        if case.get("skipped", False):
            continue
        predicted = set(case.get("predicted_rule_ids", []))
        expected = set(case.get("expected_rule_ids", []))
        for r in predicted:
            if r in expected:
                rule_tp[r] += 1
            else:
                rule_fp[r] += 1
        for r in expected:
            if r not in predicted:
                rule_fn[r] += 1

    all_rules = sorted(set(rule_tp) | set(rule_fp) | set(rule_fn))
    registry = {}
    for rule in all_rules:
        tp = rule_tp[rule]
        fp = rule_fp[rule]
        fn = rule_fn[rule]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        # Harmonic trust: weights precision 2x because FPs destroy user trust faster
        trust = (3 * prec * rec) / (2 * prec + rec + 1e-9) if (prec + rec) > 0 else 0

        if trust < 0.20:
            verdict = "suppress"
        elif trust < 0.40:
            verdict = "noisy"
        elif trust < 0.60:
            verdict = "moderate"
        else:
            verdict = "trusted"

        required_engines = 1 if trust >= 0.60 else 2

        registry[rule] = {
            "precision_score": round(prec, 4),
            "recall_score": round(rec, 4),
            "trust_score": round(trust, 4),
            "last_calibrated": "2026-04-10",
            "calibration_source": "ACT-subset-v1",
            "verdict": verdict,
            "required_engines": required_engines,
        }

    # Print summary
    total_tp = sum(rule_tp.values())
    total_fp = sum(rule_fp.values())
    total_fn = sum(rule_fn.values())
    print(f"Total rules analyzed: {len(all_rules)}")
    print(f"Total TP={total_tp} FP={total_fp} FN={total_fn}")
    overall_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    overall_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    print(f"Overall Precision={overall_prec:.4f}  Recall={overall_rec:.4f}")
    print()
    for r in sorted(registry, key=lambda x: registry[x]["trust_score"]):
        m = registry[r]
        print(
            f"  {r:35s} P={m['precision_score']:.3f} R={m['recall_score']:.3f} "
            f"T={m['trust_score']:.3f} [{m['verdict']:>10s}]"
        )

    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
    print(f"\nSaved: {OUTPUT}")


if __name__ == "__main__":
    main()
