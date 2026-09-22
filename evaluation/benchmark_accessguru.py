"""Run AccessGuru semantic baseline evaluation for Phase 1 gap analysis."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.services.heuristics import HeuristicAnalyzer
from app.services.static_checks import StaticChecker
from evaluation.accessguru_loader import AccessGuruExample, load_accessguru_examples


def _default_output() -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return Path("evaluation/results") / f"accessguru_semantic_baseline_{stamp}.json"


def _detect(example: AccessGuruExample) -> tuple[bool, list[str]]:
    html = f"<html><head><title>AccessGuru</title></head><body>{example.html_snippet}</body></html>"
    url = "file://accessguru/snippet"

    static_issues = StaticChecker(html, url).run_all()
    heuristic_issues = HeuristicAnalyzer(html, url).run_all()

    findings = [*static_issues, *heuristic_issues]
    sc_ids = [str(item.get("wcag_criterion", "") or "") for item in findings]
    detected = bool(example.wcag_sc and example.wcag_sc in sc_ids)
    return detected, [s for s in sc_ids if s]


def _save(results: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AccessGuru semantic baseline")
    parser.add_argument(
        "--dataset",
        default="evaluation/fixtures/accessguru/semantic.jsonl",
        help="AccessGuru dataset file (json/jsonl/csv)",
    )
    parser.add_argument(
        "--out",
        default=str(_default_output()),
        help="Output JSON path",
    )
    args = parser.parse_args()

    examples = load_accessguru_examples(args.dataset, semantic_only=True)
    if not examples:
        raise SystemExit(f"No semantic AccessGuru rows found in {args.dataset}")

    by_type = defaultdict(lambda: {"total": 0, "detected": 0})
    rows: list[dict] = []

    for idx, example in enumerate(examples):
        detected, detected_sc_ids = _detect(example)
        bucket = by_type[example.violation_type]
        bucket["total"] += 1
        if detected:
            bucket["detected"] += 1

        rows.append(
            {
                "row": idx,
                "violation_type": example.violation_type,
                "category": example.category,
                "wcag_sc": example.wcag_sc,
                "detected": detected,
                "detected_sc_ids": detected_sc_ids,
            }
        )

    violation_type_recall: dict[str, dict] = {}
    uncovered_violation_types: list[str] = []
    total = 0
    detected_total = 0

    for violation_type, stats in sorted(by_type.items()):
        t = int(stats["total"])
        d = int(stats["detected"])
        recall = (d / t) if t > 0 else 0.0
        violation_type_recall[violation_type] = {
            "total": t,
            "detected": d,
            "recall": round(recall, 4),
        }
        total += t
        detected_total += d
        if d == 0:
            uncovered_violation_types.append(violation_type)

    results = {
        "dataset": "accessguru_semantic",
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "rows": rows,
        "semantic_recall": round((detected_total / total) if total else 0.0, 4),
        "semantic_total": total,
        "semantic_detected": detected_total,
        "violation_type_recall": violation_type_recall,
        "gap_table": {
            "uncovered_violation_types": uncovered_violation_types,
            "uncovered_count": len(uncovered_violation_types),
        },
    }

    output_path = _save(results, Path(args.out))
    print("=== AccessGuru Semantic Baseline ===")
    print(f"Rows: {total}")
    print(f"Semantic recall: {results['semantic_recall']:.2%}")
    print(f"Uncovered violation types: {len(uncovered_violation_types)}")
    print(f"Saved: {output_path.as_posix()}")


if __name__ == "__main__":
    main()
