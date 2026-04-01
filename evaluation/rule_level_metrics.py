#!/usr/bin/env python3
"""
Compute rule-level precision/recall/F1 from benchmark results.

Usage:
python evaluation/rule_level_metrics.py \
  --results evaluation/benchmark_results_high_precision_recall_boost_full.json \
  --out evaluation/rule_level_metrics_high_precision_recall_boost_full.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def _safe_div(num: float, den: float) -> float:
    return (num / den) if den else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rule-level benchmark metrics")
    parser.add_argument("--results", required=True, help="Path to benchmark results JSON")
    parser.add_argument("--out", required=True, help="Path to save rule-level metrics JSON")
    parser.add_argument("--top", type=int, default=20, help="Top N rules for FP/FN summaries")
    args = parser.parse_args()

    results_path = Path(args.results)
    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")

    data = json.loads(results_path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])

    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    support = defaultdict(int)

    for case in cases:
        expected = set(case.get("expected_rule_ids", []))
        predicted = set(case.get("predicted_rule_ids", []))

        for r in expected:
            support[r] += 1

        for r in predicted:
            if r in expected:
                tp[r] += 1
            else:
                fp[r] += 1

        for r in expected - predicted:
            fn[r] += 1

    all_rules = set(tp) | set(fp) | set(fn) | set(support)
    per_rule = {}

    for r in sorted(all_rules):
        p = _safe_div(tp[r], tp[r] + fp[r])
        rec = _safe_div(tp[r], tp[r] + fn[r])
        f1 = _safe_div(2 * p * rec, p + rec)
        per_rule[r] = {
            "tp": tp[r],
            "fp": fp[r],
            "fn": fn[r],
            "support": support[r],
            "precision": round(p, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    top_fp = sorted(
        [{"rule_id": r, "fp": fp[r], "tp": tp[r], "support": support[r]} for r in all_rules],
        key=lambda x: x["fp"],
        reverse=True,
    )[: args.top]

    top_fn = sorted(
        [{"rule_id": r, "fn": fn[r], "tp": tp[r], "support": support[r]} for r in all_rules],
        key=lambda x: x["fn"],
        reverse=True,
    )[: args.top]

    report = {
        "profile": data.get("profile"),
        "scan_mode": data.get("scan_mode"),
        "source_results": str(results_path),
        "rules_count": len(all_rules),
        "top_false_positives": top_fp,
        "top_false_negatives": top_fn,
        "per_rule": per_rule,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== Rule-level Metrics ===")
    print(f"Source: {results_path}")
    print(f"Profile: {report['profile']} | Scan mode: {report['scan_mode']}")
    print(f"Rules analyzed: {report['rules_count']}")
    print("Top FP rules:")
    for item in top_fp[:10]:
        print(f"  {item['rule_id']}: FP={item['fp']} TP={item['tp']} support={item['support']}")
    print("Top FN rules:")
    for item in top_fn[:10]:
        print(f"  {item['rule_id']}: FN={item['fn']} TP={item['tp']} support={item['support']}")
    print(f"Saved: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
