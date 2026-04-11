"""
Rule-level metrics analyzer for post-iteration evaluation.

Reads a benchmark_results.json and produces per-rule FP/FN counts,
contribution to overall precision/recall, and suppression impact analysis.

Usage:
    python evaluation/rule_level_metrics.py evaluation/calib_iter1_act.json \
        --out evaluation/rule_level_metrics_iter1.json
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def analyze_rule_metrics(benchmark_results: dict, count_unknown_as_fp: bool = True) -> dict:
    """Analyze per-rule precision and recall contribution."""
    cases = benchmark_results.get("cases", [])
    rule_tp: Counter = Counter()
    rule_fp: Counter = Counter()
    rule_fn: Counter = Counter()
    rule_total_predicted: Counter = Counter()
    rule_total_expected: Counter = Counter()

    for case in cases:
        if case.get("skipped", False):
            continue

        predicted = set(case.get("predicted_rule_ids", []))
        expected = set(case.get("expected_rule_ids", []))
        known_valid = set(case.get("known_valid_rule_ids", expected))
        known_invalid = set(case.get("known_invalid_rule_ids", []))

        for rule in predicted:
            rule_total_predicted[rule] += 1
            if rule in known_valid:
                rule_tp[rule] += 1
            elif rule in known_invalid:
                rule_fp[rule] += 1
            elif count_unknown_as_fp:
                # Strict mode: any unexpected prediction is treated as FP.
                rule_fp[rule] += 1

        for rule in known_valid:
            rule_total_expected[rule] += 1
            if rule not in predicted:
                rule_fn[rule] += 1

    # Build per-rule metrics
    all_rules = sorted(set(rule_tp.keys()) | set(rule_fp.keys()) | set(rule_fn.keys()))
    per_rule = []
    for rule in all_rules:
        tp = rule_tp[rule]
        fp = rule_fp[rule]
        fn = rule_fn[rule]
        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / (tp + fn) if (tp + fn) > 0 else None

        per_rule.append({
            "rule_id": rule,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "total_predicted": rule_total_predicted[rule],
            "total_expected": rule_total_expected[rule],
        })

    # Sort by FP count (descending) to surface worst offenders
    per_rule.sort(key=lambda x: (-x["fp"], -x["fn"], x["rule_id"]))

    # Aggregate
    total_fp = sum(rule_fp.values())
    total_fn = sum(rule_fn.values())
    total_tp = sum(rule_tp.values())

    # Top FP contributors
    top_fp_rules = [
        {"rule_id": r["rule_id"], "fp_count": r["fp"], "fp_share": round(r["fp"] / max(1, total_fp), 3)}
        for r in per_rule[:10] if r["fp"] > 0
    ]

    # Top FN contributors (recall gaps)
    fn_sorted = sorted(per_rule, key=lambda x: -x["fn"])
    top_fn_rules = [
        {"rule_id": r["rule_id"], "fn_count": r["fn"], "fn_share": round(r["fn"] / max(1, total_fn), 3)}
        for r in fn_sorted[:10] if r["fn"] > 0
    ]

    return {
        "fp_mode": "strict" if count_unknown_as_fp else "adjudicated_only",
        "total_rules_analyzed": len(all_rules),
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "overall_precision": round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else None,
        "overall_recall": round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else None,
        "top_fp_contributors": top_fp_rules,
        "top_fn_contributors": top_fn_rules,
        "per_rule_metrics": per_rule,
        "single_rule_fp_dominance_warning": any(
            r.get("fp_share", 0) > 0.30 for r in top_fp_rules
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze per-rule precision/recall metrics")
    parser.add_argument("benchmark_results", help="Path to benchmark results JSON")
    parser.add_argument("--out", default="evaluation/rule_level_metrics.json")
    parser.add_argument(
        "--adjudicated",
        action="store_true",
        help="Only count known_invalid labels as FP (exclude unexpected unknown predictions).",
    )
    args = parser.parse_args()

    results_path = Path(args.benchmark_results)
    if not results_path.exists():
        print(f"Error: {results_path} not found", file=sys.stderr)
        sys.exit(1)

    with results_path.open("r", encoding="utf-8") as f:
        benchmark_results = json.load(f)

    metrics = analyze_rule_metrics(benchmark_results, count_unknown_as_fp=not args.adjudicated)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("=== Rule-Level Metrics ===")
    print(f"FP mode: {metrics.get('fp_mode', 'strict')}")
    print(f"Rules analyzed: {metrics['total_rules_analyzed']}")
    print(f"Overall | TP={metrics['total_tp']}  FP={metrics['total_fp']}  FN={metrics['total_fn']}")
    if metrics['overall_precision'] is not None:
        print(f"Precision: {metrics['overall_precision']:.2%}")
    if metrics['overall_recall'] is not None:
        print(f"Recall:    {metrics['overall_recall']:.2%}")
    print()

    if metrics["top_fp_contributors"]:
        print("Top FP contributors:")
        for r in metrics["top_fp_contributors"][:5]:
            print(f"  {r['rule_id']:30s}  FP={r['fp_count']:3d}  ({r['fp_share']:.0%} of total)")

    if metrics["top_fn_contributors"]:
        print("Top FN contributors (recall gaps):")
        for r in metrics["top_fn_contributors"][:5]:
            print(f"  {r['rule_id']:30s}  FN={r['fn_count']:3d}  ({r['fn_share']:.0%} of total)")

    if metrics.get("single_rule_fp_dominance_warning"):
        print("\n⚠️  WARNING: A single rule contributes >30% of total FP. Review structural policy.")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
