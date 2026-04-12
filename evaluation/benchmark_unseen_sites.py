"""
Benchmark BEACON against 10 previously unbenchmarked public sites.

Outputs a standalone artifact:
  evaluation/unseen_sites_benchmark_results.json
"""

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from app.services.audit_runner import run_audit


SITES = [
    {"name": "Sugar Labs", "url": "https://www.sugarlabs.org", "category": "nonprofit", "expected": "medium"},
    {"name": "Lichess", "url": "https://lichess.org", "category": "web-app", "expected": "medium"},
    {"name": "Wikipedia", "url": "https://www.wikipedia.org", "category": "knowledge", "expected": "high"},
    {"name": "NASA", "url": "https://www.nasa.gov", "category": "government", "expected": "medium"},
    {"name": "GNU", "url": "https://www.gnu.org", "category": "opensource", "expected": "medium"},
    {"name": "Khan Academy", "url": "https://www.khanacademy.org", "category": "education", "expected": "medium"},
    {"name": "OpenStreetMap", "url": "https://www.openstreetmap.org", "category": "maps", "expected": "medium"},
    {"name": "DuckDuckGo", "url": "https://duckduckgo.com", "category": "search", "expected": "medium"},
    {"name": "Reddit", "url": "https://www.reddit.com", "category": "social", "expected": "low"},
    {"name": "Coursera", "url": "https://www.coursera.org", "category": "education", "expected": "medium"},
]

TIER_ORDER = {"low": 0, "medium": 1, "high": 2}


def score_to_tier(score: float) -> str:
    if score >= 85.0:
        return "high"
    if score >= 70.0:
        return "medium"
    return "low"


def expected_alignment(expected: str, predicted: str) -> tuple[bool, int]:
    exp = str(expected).strip().lower()
    pred = str(predicted).strip().lower()
    if exp not in TIER_ORDER or pred not in TIER_ORDER:
        return False, 2
    distance = abs(TIER_ORDER[pred] - TIER_ORDER[exp])
    return distance == 0, distance


def is_access_limited(result: dict, issues: list[dict]) -> bool:
    if bool(result.get("degraded_mode", False)) and str(result.get("degraded_reason", "")).strip().lower() == "blocked_request":
        return True
    rule_ids = {str(i.get("rule_id") or "").strip().lower() for i in issues}
    return bool({"blocked-request-partial", "fetch-unavailable"} & rule_ids)


async def audit_site(site: dict, scan_mode: str) -> dict:
    start = time.time()
    try:
        result = await run_audit(
            site["url"],
            scan_mode=scan_mode,
            precision_profile="production",
            enable_enrichment=False,
            enable_cognitive=False,
            use_cache=False,
        )
        elapsed = round(time.time() - start, 2)
        issues = result.get("issues", [])

        severity_counts = defaultdict(int)
        rule_counts = defaultdict(int)
        for issue in issues:
            severity_counts[issue.get("severity", "unknown")] += 1
            rule_counts[issue.get("rule_id", "unknown")] += 1

        confidences = [float(i.get("confidence", 0) or 0) for i in issues]
        avg_conf = (sum(confidences) / len(confidences)) if confidences else 0.0

        score = float(result.get("score", 0) or 0)
        access_limited = is_access_limited(result, issues)
        predicted = "access-limited" if access_limited else score_to_tier(score)
        aligned, distance = expected_alignment(site.get("expected", ""), predicted)
        alignment_applicable = not access_limited
        if not alignment_applicable:
            aligned = False
            distance = 0

        pt = result.get("precision_profile_telemetry", {})

        return {
            "name": site["name"],
            "url": site["url"],
            "category": site["category"],
            "scan_mode": scan_mode,
            "success": True,
            "score": score,
            "total_issues": len(issues),
            "avg_confidence": round(avg_conf, 3),
            "scan_time_s": elapsed,
            "degraded_mode": bool(result.get("degraded_mode", False)),
            "degraded_reason": result.get("degraded_reason"),
            "access_limited": access_limited,
            "expected_tier": site["expected"],
            "predicted_tier": predicted,
            "expected_alignment": aligned,
            "expected_alignment_distance": distance,
            "alignment_applicable": alignment_applicable,
            "top_rules": [
                {"rule": rid, "count": count}
                for rid, count in sorted(rule_counts.items(), key=lambda x: -x[1])[:5]
            ],
            "severity": dict(severity_counts),
            "telemetry": {
                "input_issues": pt.get("input_issues", 0),
                "reported_issues": pt.get("reported_issues", 0),
                "dropped_structural": pt.get("dropped_structural", 0),
                "dropped_low_confidence": pt.get("dropped_low_confidence", 0),
                "suppression_rate": pt.get("suppression_rate", 0),
                "suppression_warning": pt.get("suppression_warning", False),
                "low_issue_guard_active": pt.get("low_issue_guard_active", False),
            },
            "error": None,
        }
    except Exception as exc:
        elapsed = round(time.time() - start, 2)
        return {
            "name": site["name"],
            "url": site["url"],
            "category": site["category"],
            "scan_mode": scan_mode,
            "success": False,
            "score": 0.0,
            "total_issues": 0,
            "avg_confidence": 0.0,
            "scan_time_s": elapsed,
            "degraded_mode": True,
            "degraded_reason": "exception",
            "access_limited": True,
            "expected_tier": site["expected"],
            "predicted_tier": "unknown",
            "expected_alignment": False,
            "expected_alignment_distance": 2,
            "alignment_applicable": False,
            "top_rules": [],
            "severity": {},
            "telemetry": {},
            "error": str(exc)[:300],
        }


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return float(values[int(len(values) * 0.95)])


def summarize(mode_results: list[dict]) -> dict:
    successful = [r for r in mode_results if r.get("success")]
    if not successful:
        return {
            "successful_sites": 0,
            "avg_score": 0.0,
            "avg_scan_time_s": 0.0,
            "p95_scan_time_s": 0.0,
            "avg_confidence": 0.0,
            "avg_issues": 0.0,
            "suppression_warnings": 0,
            "access_limited_sites": 0,
            "alignment_applicable_sites": 0,
            "alignment_rate": 0.0,
        }

    scores = [float(r.get("score", 0) or 0) for r in successful]
    times = [float(r.get("scan_time_s", 0) or 0) for r in successful]
    confs = [float(r.get("avg_confidence", 0) or 0) for r in successful if float(r.get("avg_confidence", 0) or 0) > 0]
    issues = [int(r.get("total_issues", 0) or 0) for r in successful]

    applicable = [r for r in successful if bool(r.get("alignment_applicable", True))]
    aligned = sum(1 for r in applicable if bool(r.get("expected_alignment", False)))

    return {
        "successful_sites": len(successful),
        "avg_score": round(sum(scores) / len(scores), 3),
        "avg_scan_time_s": round(sum(times) / len(times), 3),
        "p95_scan_time_s": round(p95(times), 3),
        "avg_confidence": round((sum(confs) / len(confs)) if confs else 0.0, 3),
        "avg_issues": round(sum(issues) / len(issues), 3),
        "suppression_warnings": sum(1 for r in successful if bool((r.get("telemetry") or {}).get("suppression_warning", False))),
        "access_limited_sites": sum(1 for r in successful if bool(r.get("access_limited", False))),
        "alignment_applicable_sites": len(applicable),
        "alignment_rate": round((aligned / len(applicable)) if applicable else 0.0, 4),
    }


async def main() -> None:
    all_results = {"fast": [], "deep": []}

    print("Running unseen-sites benchmark for fast and deep modes...")
    for mode in ["fast", "deep"]:
        print(f"\nMode: {mode}")
        for site in SITES:
            result = await audit_site(site, mode)
            all_results[mode].append(result)
            icon = "OK" if result["success"] else "ERR"
            print(
                f"  [{icon}] {site['name']:<16} score={result['score']:>5.1f} "
                f"issues={result['total_issues']:>3} time={result['scan_time_s']:>5.2f}s "
                f"access_limited={'yes' if result.get('access_limited') else 'no'}"
            )

    fast_summary = summarize(all_results["fast"])
    deep_summary = summarize(all_results["deep"])

    total_success = fast_summary["successful_sites"] + deep_summary["successful_sites"]
    expected_total = len(SITES) * 2
    runtime_success_rate = round(total_success / expected_total, 4) if expected_total else 0.0

    overall = {
        "runtime_success_rate": runtime_success_rate,
        "successful_audits": total_success,
        "expected_audits": expected_total,
        "total_access_limited_audits": fast_summary["access_limited_sites"] + deep_summary["access_limited_sites"],
        "total_suppression_warnings": fast_summary["suppression_warnings"] + deep_summary["suppression_warnings"],
        "combined_alignment_rate": round(
            (
                (fast_summary["alignment_rate"] * fast_summary["alignment_applicable_sites"])
                + (deep_summary["alignment_rate"] * deep_summary["alignment_applicable_sites"])
            )
            / max(1, fast_summary["alignment_applicable_sites"] + deep_summary["alignment_applicable_sites"]),
            4,
        ),
    }

    payload = {
        "sites": SITES,
        "fast": all_results["fast"],
        "deep": all_results["deep"],
        "summary": {
            "fast": fast_summary,
            "deep": deep_summary,
            "overall": overall,
        },
    }

    out_path = Path("evaluation/unseen_sites_benchmark_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    print("\nSaved benchmark artifact:", out_path)
    print("Runtime success rate:", f"{runtime_success_rate:.0%}")


if __name__ == "__main__":
    asyncio.run(main())
