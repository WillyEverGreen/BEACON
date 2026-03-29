"""
Reliability gate for benchmark repeatability.

This script does not promise perfect real-world accuracy (no system can),
but it guarantees that a profile is only accepted if it consistently meets
minimum precision/recall thresholds across repeated runs.

Example:
python evaluation/reliability_gate.py \
  evaluation/benchmark_cases_20.json \
  --profiles high_precision strict balanced \
  --repeats 3 \
  --scan-mode fast \
  --metric micro \
  --min-precision 0.10 \
  --min-recall 0.20
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _metric_block(results: dict[str, Any], metric: str) -> dict[str, Any]:
    agg = results.get("aggregate", {})
    if metric == "micro":
        return agg.get("micro", {})
    if metric == "adjudicated_micro":
        return agg.get("adjudicated_micro", {})
    raise ValueError(f"Unknown metric: {metric}")


def _run_once(
    benchmark_file: Path,
    profile: str,
    scan_mode: str,
    out_file: Path,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "evaluation/benchmark_precision_recall.py",
        str(benchmark_file),
        "--profile",
        profile,
        "--scan-mode",
        scan_mode,
        "--out",
        str(out_file),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Benchmark run failed for profile={profile}.\n"
            f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
        )
    return _load_json(out_file)


def _summarize_runs(run_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    precisions = [m.get("precision", 0.0) for m in run_metrics]
    recalls = [m.get("recall", 0.0) for m in run_metrics]
    f1s = [m.get("f1", 0.0) for m in run_metrics]

    def _stats(values: list[float]) -> dict[str, float]:
        return {
            "min": min(values) if values else 0.0,
            "max": max(values) if values else 0.0,
            "mean": statistics.mean(values) if values else 0.0,
            "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        }

    return {
        "precision": _stats(precisions),
        "recall": _stats(recalls),
        "f1": _stats(f1s),
        "runs": len(run_metrics),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reliability gate for benchmark precision/recall")
    parser.add_argument("benchmark_file", help="Path to benchmark JSON")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["high_precision", "strict", "balanced"],
        help="Profiles to evaluate",
    )
    parser.add_argument("--repeats", type=int, default=3, help="Number of repeated runs per profile")
    parser.add_argument("--scan-mode", choices=["fast", "deep"], default="fast")
    parser.add_argument(
        "--metric",
        choices=["micro", "adjudicated_micro"],
        default="micro",
        help="Metric space used by the gate",
    )
    parser.add_argument("--min-precision", type=float, default=0.10)
    parser.add_argument("--min-recall", type=float, default=0.20)
    parser.add_argument(
        "--out",
        default="evaluation/reliability_gate_report.json",
        help="Path to save gate report",
    )
    args = parser.parse_args()

    benchmark_file = Path(args.benchmark_file)
    if not benchmark_file.exists():
        raise FileNotFoundError(f"Benchmark file not found: {benchmark_file}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    profile_reports: list[dict[str, Any]] = []

    for profile in args.profiles:
        run_metrics: list[dict[str, Any]] = []
        run_files: list[str] = []

        for i in range(1, args.repeats + 1):
            run_out = out_path.parent / f"gate_{profile}_run{i}.json"
            results = _run_once(benchmark_file, profile, args.scan_mode, run_out)
            metrics = _metric_block(results, args.metric)
            run_metrics.append(metrics)
            run_files.append(str(run_out))

        summary = _summarize_runs(run_metrics)
        min_precision = summary["precision"]["min"]
        min_recall = summary["recall"]["min"]
        passed = (min_precision >= args.min_precision) and (min_recall >= args.min_recall)

        profile_reports.append(
            {
                "profile": profile,
                "passed": passed,
                "thresholds": {
                    "min_precision": args.min_precision,
                    "min_recall": args.min_recall,
                },
                "summary": summary,
                "run_files": run_files,
            }
        )

    passing = [p for p in profile_reports if p["passed"]]
    # Pick the most conservative winner among passing profiles:
    # highest minimum precision, tie-breaker highest mean recall.
    passing_sorted = sorted(
        passing,
        key=lambda p: (
            p["summary"]["precision"]["min"],
            p["summary"]["recall"]["mean"],
        ),
        reverse=True,
    )
    recommended = passing_sorted[0]["profile"] if passing_sorted else None

    report = {
        "benchmark_file": str(benchmark_file),
        "scan_mode": args.scan_mode,
        "metric": args.metric,
        "repeats": args.repeats,
        "thresholds": {
            "min_precision": args.min_precision,
            "min_recall": args.min_recall,
        },
        "profiles": profile_reports,
        "recommended_profile": recommended,
        "gate_passed": recommended is not None,
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=== Reliability Gate ===")
    print(f"Benchmark: {benchmark_file}")
    print(f"Metric: {args.metric} | Repeats: {args.repeats} | Scan mode: {args.scan_mode}")
    print(f"Thresholds -> precision >= {args.min_precision:.2%}, recall >= {args.min_recall:.2%}")

    for p in profile_reports:
        s = p["summary"]
        print("---")
        print(f"Profile: {p['profile']} | PASS: {p['passed']}")
        print(
            f"Min precision={s['precision']['min']:.2%}, "
            f"Min recall={s['recall']['min']:.2%}, "
            f"Mean F1={s['f1']['mean']:.2%}"
        )

    print("---")
    if recommended:
        print(f"Recommended profile: {recommended}")
        print(f"Saved report: {out_path}")
        return 0

    print("No profile met the reliability thresholds.")
    print(f"Saved report: {out_path}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
