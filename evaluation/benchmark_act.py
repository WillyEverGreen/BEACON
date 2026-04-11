"""
ACT benchmark runner with automatic trust-registry recalibration.

This wrapper executes the ACT benchmark, computes per-rule TP/FP/FN metrics,
and feeds them into the adaptive trust registry so each run improves future scans.
"""

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from evaluation.benchmark_precision_recall import _run_all
from app.services.rule_calibrator import recalibrate_from_act_results, get_trust_summary


def _build_per_rule_metrics(results: dict) -> dict[str, dict]:
    rule_tp: Counter[str] = Counter()
    rule_fp: Counter[str] = Counter()
    rule_fn: Counter[str] = Counter()

    for case in results.get("cases", []):
        if case.get("skipped", False):
            continue

        predicted = set(case.get("predicted_rule_ids", []))
        expected = set(case.get("expected_rule_ids", []))

        for rule_id in predicted:
            if rule_id in expected:
                rule_tp[rule_id] += 1
            else:
                rule_fp[rule_id] += 1

        for rule_id in expected:
            if rule_id not in predicted:
                rule_fn[rule_id] += 1

    all_rules = set(rule_tp) | set(rule_fp) | set(rule_fn)
    out: dict[str, dict] = {}
    for rule_id in all_rules:
        tp = int(rule_tp[rule_id])
        fp = int(rule_fp[rule_id])
        fn = int(rule_fn[rule_id])
        precision = (tp / (tp + fp)) if (tp + fp) > 0 else None
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else None
        out[rule_id] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ACT benchmark and auto-recalibrate trust registry")
    parser.add_argument(
        "--benchmark-file",
        default="evaluation/benchmark_cases_20.json",
        help="Path to ACT benchmark case file",
    )
    parser.add_argument(
        "--profile",
        choices=[
            "balanced",
            "tuned_balanced",
            "high_precision",
            "high_precision_plus",
            "high_precision_recall_boost",
            "high_precision_recall_strict",
            "high_precision_recall_balanced",
            "high_precision_recall_exploratory",
            "strict",
            "very_high_precision",
            "medium_precision",
            "ultra_strict",
            "production",
        ],
        default="production",
    )
    parser.add_argument("--scan-mode", choices=["fast", "deep"], default="fast")
    parser.add_argument("--out", default="evaluation/retest_act_latest.json")
    args = parser.parse_args()

    benchmark_path = Path(args.benchmark_file)
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {benchmark_path}")

    with benchmark_path.open("r", encoding="utf-8") as f:
        benchmark = json.load(f)

    results = asyncio.run(_run_all(benchmark, args.profile, args.scan_mode))

    per_rule_metrics = _build_per_rule_metrics(results)
    results["per_rule_metrics"] = per_rule_metrics
    results["recalibration"] = {
        "enabled": True,
        "profile": args.profile,
        "scan_mode": args.scan_mode,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    recalibrate_from_act_results(results)
    trust_summary = get_trust_summary()

    micro = results.get("aggregate", {}).get("micro", {})
    adj = results.get("aggregate", {}).get("adjudicated_micro", {})

    print("=== ACT Benchmark (with Auto-Recalibration) ===")
    print(f"Benchmark file: {benchmark_path}")
    print(f"Profile: {args.profile} | Scan mode: {args.scan_mode}")
    print(
        "Evaluated/skipped cases: "
        f"{results.get('act_evaluated_cases', 0)}/{results.get('act_skipped_cases', 0)}"
    )

    if micro.get("precision") is None:
        print("Micro Precision: skipped")
        print("Micro Recall:    skipped")
        print("Micro F1:        skipped")
    else:
        print(f"Micro Precision: {float(micro.get('precision', 0.0)):.2%}")
        print(f"Micro Recall:    {float(micro.get('recall', 0.0)):.2%}")
        print(f"Micro F1:        {float(micro.get('f1', 0.0)):.2%}")

    if adj.get("precision") is not None:
        print("---")
        print(f"Adjudicated Precision: {float(adj.get('precision', 0.0)):.2%}")
        print(f"Adjudicated Recall:    {float(adj.get('recall', 0.0)):.2%}")
        print(f"Adjudicated F1:        {float(adj.get('f1', 0.0)):.2%}")

    print(f"Per-rule metrics updated: {len(per_rule_metrics)}")
    print(
        "Trust registry summary: "
        f"rules={trust_summary.get('total_rules', 0)}, "
        f"avg_trust={trust_summary.get('avg_trust_score', 0.0)}"
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
