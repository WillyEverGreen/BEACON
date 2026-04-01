"""
Benchmark precision/recall evaluator for accessibility detection quality.

Supports two labeling modes:
1) Legacy partial labels:
     - expected_rule_ids: known positives only (recall-oriented)
2) Adjudicated labels (recommended for precision claims):
     - known_valid_rule_ids: manually verified true issues
     - known_invalid_rule_ids: manually verified false issues

Input JSON format:
{
    "cases": [
        {
            "name": "home page",
            "url": "https://example.com",
            "expected_rule_ids": ["missing-label", "empty-link"],
            "known_valid_rule_ids": ["missing-label", "empty-link"],
            "known_invalid_rule_ids": ["no-headings"]
        }
    ]
}

Usage:
python evaluation/benchmark_precision_recall.py benchmark.json --profile high_precision
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from app.services.audit_runner import run_audit


def _calc_metrics(expected: set[str], predicted: set[str]) -> dict:
    tp = len(expected & predicted)
    fp = len(predicted - expected)
    fn = len(expected - predicted)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _calc_adjudicated_metrics(
    known_valid: set[str],
    known_invalid: set[str],
    predicted: set[str],
) -> dict:
    """
    Compute precision/recall using only manually adjudicated labels.

    Unknown rules (not in known_valid or known_invalid) are excluded from
    precision denominator to avoid penalizing partially-labeled datasets.
    """
    adjudicated_space = known_valid | known_invalid
    predicted_in_space = predicted & adjudicated_space

    tp = len(predicted_in_space & known_valid)
    fp = len(predicted_in_space & known_invalid)
    fn = len(known_valid - predicted)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "adjudicated_rule_count": len(adjudicated_space),
        "predicted_in_adjudicated_space": len(predicted_in_space),
        "unknown_predicted_rule_count": len(predicted - adjudicated_space),
    }


async def _run_case(case: dict, profile: str, scan_mode: str) -> dict:
    result = await run_audit(
        case["url"],
        scan_mode=scan_mode,
        precision_profile=profile,
        enable_enrichment=False,
        enable_cognitive=False,
    )

    predicted_rules = {i.get("rule_id", "") for i in result.get("issues", []) if i.get("rule_id")}
    expected_rules = set(case.get("expected_rule_ids", []))
    known_valid_rules = set(case.get("known_valid_rule_ids", expected_rules))
    known_invalid_rules = set(case.get("known_invalid_rule_ids", []))

    metrics = _calc_metrics(expected_rules, predicted_rules)
    adjudicated_metrics = _calc_adjudicated_metrics(known_valid_rules, known_invalid_rules, predicted_rules)
    return {
        "name": case.get("name", case.get("url", "case")),
        "url": case.get("url"),
        "expected_rule_ids": sorted(expected_rules),
        "predicted_rule_ids": sorted(predicted_rules),
        "missing_rule_ids": sorted(expected_rules - predicted_rules),
        "unexpected_rule_ids": sorted(predicted_rules - expected_rules),
        "metrics": metrics,
        "adjudicated_metrics": adjudicated_metrics,
        "scan_summary": result.get("summary", ""),
        "precision_profile_telemetry": result.get("precision_profile_telemetry", {}),
        "rule_activity": result.get("rule_activity", {}),
    }


async def _run_all(benchmark: dict, profile: str, scan_mode: str) -> dict:
    cases = benchmark.get("cases", [])
    if not cases:
        raise ValueError("Benchmark file must contain a non-empty 'cases' list")

    per_case = []
    total_tp = total_fp = total_fn = 0
    total_adj_tp = total_adj_fp = total_adj_fn = 0

    for case in cases:
        if "url" not in case:
            raise ValueError(f"Case missing 'url': {case}")
        case_result = await _run_case(case, profile, scan_mode)
        per_case.append(case_result)

        m = case_result["metrics"]
        total_tp += m["tp"]
        total_fp += m["fp"]
        total_fn += m["fn"]

        am = case_result["adjudicated_metrics"]
        total_adj_tp += am["tp"]
        total_adj_fp += am["fp"]
        total_adj_fn += am["fn"]

    macro_precision = sum(c["metrics"]["precision"] for c in per_case) / len(per_case)
    macro_recall = sum(c["metrics"]["recall"] for c in per_case) / len(per_case)
    macro_f1 = sum(c["metrics"]["f1"] for c in per_case) / len(per_case)

    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if (micro_precision + micro_recall)
        else 0.0
    )

    adj_micro_precision = total_adj_tp / (total_adj_tp + total_adj_fp) if (total_adj_tp + total_adj_fp) else 0.0
    adj_micro_recall = total_adj_tp / (total_adj_tp + total_adj_fn) if (total_adj_tp + total_adj_fn) else 0.0
    adj_micro_f1 = (
        2 * adj_micro_precision * adj_micro_recall / (adj_micro_precision + adj_micro_recall)
        if (adj_micro_precision + adj_micro_recall)
        else 0.0
    )

    return {
        "profile": profile,
        "scan_mode": scan_mode,
        "cases": per_case,
        "aggregate": {
            "micro": {
                "precision": round(micro_precision, 4),
                "recall": round(micro_recall, 4),
                "f1": round(micro_f1, 4),
                "tp": total_tp,
                "fp": total_fp,
                "fn": total_fn,
            },
            "adjudicated_micro": {
                "precision": round(adj_micro_precision, 4),
                "recall": round(adj_micro_recall, 4),
                "f1": round(adj_micro_f1, 4),
                "tp": total_adj_tp,
                "fp": total_adj_fp,
                "fn": total_adj_fn,
            },
            "macro": {
                "precision": round(macro_precision, 4),
                "recall": round(macro_recall, 4),
                "f1": round(macro_f1, 4),
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark accessibility precision/recall")
    parser.add_argument("benchmark_file", help="Path to benchmark JSON")
    parser.add_argument("--profile", choices=["balanced", "tuned_balanced", "high_precision", "high_precision_plus", "high_precision_recall_boost", "high_precision_recall_strict", "high_precision_recall_balanced", "high_precision_recall_exploratory", "strict", "very_high_precision", "medium_precision", "ultra_strict"], default="high_precision")
    parser.add_argument("--scan-mode", choices=["fast", "deep"], default="deep")
    parser.add_argument("--out", default="evaluation/benchmark_results.json")
    args = parser.parse_args()

    benchmark_path = Path(args.benchmark_file)
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {benchmark_path}")

    with benchmark_path.open("r", encoding="utf-8") as f:
        benchmark = json.load(f)

    results = asyncio.run(_run_all(benchmark, args.profile, args.scan_mode))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    micro = results["aggregate"]["micro"]
    adj = results["aggregate"]["adjudicated_micro"]
    print("=== Benchmark Results ===")
    print(f"Profile: {args.profile} | Scan mode: {args.scan_mode}")
    print(f"Micro Precision: {micro['precision']:.2%}")
    print(f"Micro Recall:    {micro['recall']:.2%}")
    print(f"Micro F1:        {micro['f1']:.2%}")
    print(f"TP/FP/FN:        {micro['tp']}/{micro['fp']}/{micro['fn']}")
    print("---")
    print(f"Adjudicated Precision: {adj['precision']:.2%}")
    print(f"Adjudicated Recall:    {adj['recall']:.2%}")
    print(f"Adjudicated F1:        {adj['f1']:.2%}")
    print(f"Adj TP/FP/FN:          {adj['tp']}/{adj['fp']}/{adj['fn']}")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
