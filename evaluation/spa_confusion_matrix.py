"""Evaluate SPA classifier against a labeled truth set and output confusion metrics."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.audit_runner import run_audit
from app.services.spa_classifier import compute_confusion_matrix, precision_recall


async def _evaluate_case(
    case: dict[str, Any],
    *,
    semaphore: asyncio.Semaphore,
    scan_mode: str,
    precision_profile: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    name = str(case.get("name") or case.get("url") or "case")
    url = str(case.get("url") or "").strip()
    expected_is_spa = bool(case.get("is_spa", False))

    if not url:
        return {
            "name": name,
            "url": url,
            "expected_is_spa": expected_is_spa,
            "error": "missing_url",
        }

    try:
        async with semaphore:
            result = await asyncio.wait_for(
                run_audit(
                    url=url,
                    scan_mode=scan_mode,
                    precision_profile=precision_profile,
                    enable_enrichment=False,
                    max_enrich_issues=0,
                    enable_cognitive=False,
                    await_enrichment=False,
                ),
                timeout=timeout_seconds,
            )

        spa_classification = dict(result.get("spa_classification") or {})
        predicted_is_spa = bool(spa_classification.get("is_spa", result.get("is_spa", False)))
        confidence = str(spa_classification.get("confidence", "low") or "low")
        signals = [str(signal) for signal in spa_classification.get("signals", [])]
        browser_probe_metadata = dict(result.get("browser_probe_metadata") or {})
        signal_evidence = dict(browser_probe_metadata.get("spa_signal_evidence") or {})

        return {
            "name": name,
            "url": url,
            "expected_is_spa": expected_is_spa,
            "predicted_is_spa": predicted_is_spa,
            "confidence": confidence,
            "signals": signals,
            "evidence": signal_evidence,
            "spa_framework": result.get("spa_framework"),
            "degraded_mode": bool(result.get("degraded_mode", False)),
            "degraded_reason": result.get("degraded_reason") or result.get("degradation_reason"),
            "scan_time_seconds": float(result.get("scan_time_seconds", 0.0) or 0.0),
            "error": None,
        }
    except Exception as exc:
        return {
            "name": name,
            "url": url,
            "expected_is_spa": expected_is_spa,
            "error": str(exc)[:240],
        }


async def _run_evaluation(
    cases: list[dict[str, Any]],
    *,
    scan_mode: str,
    precision_profile: str,
    parallel: int,
    timeout_seconds: float,
    include_degraded: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int], float, float]:
    semaphore = asyncio.Semaphore(max(1, parallel))
    tasks = [
        _evaluate_case(
            case,
            semaphore=semaphore,
            scan_mode=scan_mode,
            precision_profile=precision_profile,
            timeout_seconds=timeout_seconds,
        )
        for case in cases
    ]
    rows = await asyncio.gather(*tasks)

    evaluated_pairs: list[tuple[bool, bool]] = []
    skipped: list[dict[str, Any]] = []

    for row in rows:
        error = row.get("error")
        if error:
            skipped.append(
                {
                    "name": row.get("name"),
                    "url": row.get("url"),
                    "reason": "error",
                    "detail": error,
                }
            )
            continue

        if bool(row.get("degraded_mode", False)) and not include_degraded:
            skipped.append(
                {
                    "name": row.get("name"),
                    "url": row.get("url"),
                    "reason": "degraded_mode",
                    "detail": row.get("degraded_reason"),
                }
            )
            continue

        evaluated_pairs.append((bool(row.get("expected_is_spa", False)), bool(row.get("predicted_is_spa", False))))

    confusion = compute_confusion_matrix(evaluated_pairs)
    precision, recall = precision_recall(confusion)
    return rows, skipped, confusion, precision, recall


def _load_truth_set(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, list):
        return payload, {}

    if not isinstance(payload, dict):
        raise ValueError("Truth set must be a JSON object or list")

    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Truth set JSON object must contain a 'cases' list")

    metadata = {
        "name": payload.get("name"),
        "description": payload.get("description"),
        "targets": payload.get("targets") if isinstance(payload.get("targets"), dict) else {},
    }
    return cases, metadata


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate SPA classifier confusion matrix")
    parser.add_argument(
        "--truth-set",
        default="evaluation/spa_truth_set.json",
        help="Path to labeled SPA truth set JSON",
    )
    parser.add_argument(
        "--scan-mode",
        choices=["deep", "max"],
        default="deep",
        help="Audit mode for SPA signal collection",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=2,
        help="Maximum concurrent audits",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=130.0,
        help="Timeout per audit case",
    )
    parser.add_argument(
        "--precision-profile",
        default="",
        help="Precision profile string used by run_audit (empty = cache-busting auto profile)",
    )
    parser.add_argument(
        "--min-precision",
        type=float,
        default=None,
        help="Override SPA precision threshold",
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=None,
        help="Override SPA recall threshold",
    )
    parser.add_argument(
        "--include-degraded",
        action="store_true",
        help="Include degraded scans in confusion-matrix evaluation",
    )
    parser.add_argument(
        "--fail-under-targets",
        action="store_true",
        help="Exit with non-zero status when precision/recall targets are not met",
    )
    parser.add_argument(
        "--out",
        default="evaluation/spa_confusion_matrix_results.json",
        help="Output JSON path",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    truth_set_path = Path(args.truth_set)
    if not truth_set_path.exists():
        raise FileNotFoundError(f"Truth set not found: {truth_set_path}")

    cases, truth_metadata = _load_truth_set(truth_set_path)
    if not cases:
        raise ValueError("Truth set contains no cases")

    targets = truth_metadata.get("targets", {}) if isinstance(truth_metadata, dict) else {}
    min_precision = float(args.min_precision if args.min_precision is not None else targets.get("spa_precision_min", 0.9))
    min_recall = float(args.min_recall if args.min_recall is not None else targets.get("spa_recall_min", 0.9))

    precision_profile = args.precision_profile.strip() or f"spa_eval_{int(time.time())}"

    started_at = time.time()
    rows, skipped, confusion, precision, recall = asyncio.run(
        _run_evaluation(
            cases,
            scan_mode=args.scan_mode,
            precision_profile=precision_profile,
            parallel=args.parallel,
            timeout_seconds=args.timeout_seconds,
            include_degraded=bool(args.include_degraded),
        )
    )
    elapsed = round(time.time() - started_at, 2)

    tp = int(confusion.get("tp", 0))
    fp = int(confusion.get("fp", 0))
    fn = int(confusion.get("fn", 0))
    tn = int(confusion.get("tn", 0))
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    precision_ok = precision >= min_precision
    recall_ok = recall >= min_recall

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "truth_set_path": str(truth_set_path),
        "truth_set_name": truth_metadata.get("name") if isinstance(truth_metadata, dict) else None,
        "scan_mode": args.scan_mode,
        "precision_profile": precision_profile,
        "targets": {
            "spa_precision_min": min_precision,
            "spa_recall_min": min_recall,
        },
        "summary": {
            "total_cases": len(cases),
            "evaluated_cases": tp + fp + fn + tn,
            "skipped_cases": len(skipped),
            "error_cases": sum(1 for row in rows if row.get("error")),
            "degraded_skipped": sum(1 for item in skipped if item.get("reason") == "degraded_mode"),
            "duration_seconds": elapsed,
        },
        "confusion_matrix": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
        },
        "metrics": {
            "spa_precision": round(precision, 4),
            "spa_recall": round(recall, 4),
            "spa_f1": round(f1, 4),
        },
        "target_validation": {
            "spa_precision_passed": precision_ok,
            "spa_recall_passed": recall_ok,
            "all_targets_passed": bool(precision_ok and recall_ok),
        },
        "cases": rows,
        "skipped": skipped,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("=== SPA Confusion Matrix ===")
    print(f"Truth set: {truth_set_path}")
    print(f"Cases evaluated: {report['summary']['evaluated_cases']} / {report['summary']['total_cases']}")
    print(f"TP/FP/FN/TN: {tp}/{fp}/{fn}/{tn}")
    print(f"SPA precision: {precision:.2%} (target {min_precision:.0%})")
    print(f"SPA recall:    {recall:.2%} (target {min_recall:.0%})")
    print(f"SPA F1:        {f1:.2%}")
    print(f"Saved: {out_path}")

    if args.fail_under_targets and not (precision_ok and recall_ok):
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
