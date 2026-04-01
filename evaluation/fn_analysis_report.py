#!/usr/bin/env python3
"""
Analyze false negatives from benchmark results and generate a targeting report.

Usage:
python evaluation/fn_analysis_report.py \
  --results evaluation/benchmark_results_high_precision_recall_strict_after_text_alternatives_rollback_full.json \
  --benchmark evaluation/benchmark_cases.json \
  --out evaluation/fn_analysis_report_current.json \
  --sample-size 100
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


def _extract_case_group(url: str) -> str:
    """Extract a stable case-group hint from ACT testcase URLs when possible."""
    if not url:
        return "unknown"
    try:
        parts = [p for p in urlparse(url).path.split("/") if p]
        # Typical ACT path: /testcases/<ruleGroup>/<caseHash>.html
        if "testcases" in parts:
            idx = parts.index("testcases")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    except Exception:
        pass
    return "unknown"


def _load_benchmark_lookup(benchmark_path: Path | None) -> dict[str, dict]:
    """Build URL -> benchmark metadata lookup."""
    if not benchmark_path or not benchmark_path.exists():
        return {}

    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    lookup: dict[str, dict] = {}
    for case in data.get("cases", []):
        url = case.get("url")
        if not url:
            continue
        lookup[url] = {
            "source_id": case.get("source_id"),
            "source_tier": case.get("source_tier"),
            "name": case.get("name"),
            "unmapped_act_rule_ids": case.get("unmapped_act_rule_ids", []),
        }
    return lookup


def build_report(results: dict, benchmark_lookup: dict[str, dict], sample_size: int, top: int) -> dict:
    cases = results.get("cases", [])
    fn_counter: Counter[str] = Counter()
    fn_case_entries: defaultdict[str, list] = defaultdict(list)
    source_counter_by_rule: defaultdict[str, Counter[str]] = defaultdict(Counter)
    case_group_counter_by_rule: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for case in cases:
        url = case.get("url", "")
        name = case.get("name", "")
        missing = case.get("missing_rule_ids", [])

        bm = benchmark_lookup.get(url, {})
        source_id = bm.get("source_id") or "unknown"
        source_tier = bm.get("source_tier")
        case_group = _extract_case_group(url)

        for rule in missing:
            fn_counter[rule] += 1
            source_counter_by_rule[rule][source_id] += 1
            case_group_counter_by_rule[rule][case_group] += 1

            if len(fn_case_entries[rule]) < sample_size:
                fn_case_entries[rule].append(
                    {
                        "name": bm.get("name") or name,
                        "url": url,
                        "source_id": source_id,
                        "source_tier": source_tier,
                        "case_group_hint": case_group,
                        "predicted_rule_ids": case.get("predicted_rule_ids", []),
                    }
                )

    total_fn = sum(fn_counter.values())

    top_fn_rules = []
    cumulative = 0
    cover_50 = []

    for rule, count in fn_counter.most_common(top):
        cumulative += count
        pct = (count / total_fn * 100.0) if total_fn else 0.0
        cumulative_pct = (cumulative / total_fn * 100.0) if total_fn else 0.0

        row = {
            "rule_id": rule,
            "fn_count": count,
            "fn_percent": round(pct, 2),
            "cumulative_fn_percent": round(cumulative_pct, 2),
            "top_sources": [
                {"source_id": sid, "count": c}
                for sid, c in source_counter_by_rule[rule].most_common(5)
            ],
            "top_case_groups": [
                {"case_group": grp, "count": c}
                for grp, c in case_group_counter_by_rule[rule].most_common(5)
            ],
            "sample_missed_cases": fn_case_entries[rule][: min(10, sample_size)],
        }
        top_fn_rules.append(row)

        if not cover_50 or cover_50[-1]["cumulative_fn_percent"] < 50.0:
            cover_50.append({"rule_id": rule, "fn_count": count, "cumulative_fn_percent": round(cumulative_pct, 2)})

    return {
        "profile": results.get("profile"),
        "scan_mode": results.get("scan_mode"),
        "source_results": results.get("source_results", ""),
        "totals": {
            "cases": len(cases),
            "tp": results.get("aggregate", {}).get("micro", {}).get("tp", 0),
            "fp": results.get("aggregate", {}).get("micro", {}).get("fp", 0),
            "fn": results.get("aggregate", {}).get("micro", {}).get("fn", 0),
            "total_fn_events": total_fn,
        },
        "top_fn_rules": top_fn_rules,
        "rules_covering_50_percent_fn": cover_50,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate FN distribution and sampling report")
    parser.add_argument("--results", required=True, help="Path to benchmark results JSON")
    parser.add_argument("--benchmark", default="evaluation/benchmark_cases.json", help="Path to benchmark cases JSON for source metadata")
    parser.add_argument("--out", required=True, help="Path to output report JSON")
    parser.add_argument("--sample-size", type=int, default=100, help="Max sampled missed cases kept per FN rule")
    parser.add_argument("--top", type=int, default=25, help="Top N FN rules to include")
    args = parser.parse_args()

    results_path = Path(args.results)
    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")

    results = json.loads(results_path.read_text(encoding="utf-8"))
    benchmark_lookup = _load_benchmark_lookup(Path(args.benchmark) if args.benchmark else None)

    report = build_report(results, benchmark_lookup, sample_size=max(1, args.sample_size), top=max(1, args.top))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== FN Analysis Report ===")
    print(f"Source results: {results_path}")
    print(f"Cases: {report['totals']['cases']} | TP/FP/FN: {report['totals']['tp']}/{report['totals']['fp']}/{report['totals']['fn']}")
    print("Top FN rules:")
    for row in report["top_fn_rules"][:10]:
        print(
            f"  {row['rule_id']}: FN={row['fn_count']} "
            f"({row['fn_percent']}%), cumulative={row['cumulative_fn_percent']}%"
        )
    print("Rules covering >=50% FN:")
    for row in report["rules_covering_50_percent_fn"]:
        print(f"  {row['rule_id']}: cumulative={row['cumulative_fn_percent']}%")
    print(f"Saved: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
