"""
Production Readiness — Comprehensive 10-Site Benchmark (Fast + Deep).

Tests the hardened production profile against 10 real-world sites spanning:
1. Government/Public services (USA.gov, IRCTC)
2. News (BBC News, NDTV) — dynamic + ads
3. E-commerce niche (Etsy, Meesho) — user-generated content
4. Dev/docs (MDN, Stack Overflow) — precision checks
5. Design/portfolio (Dribbble, Awwwards) — poor semantics

Each site is audited in BOTH fast and deep modes with the production profile.
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

BENCHMARK_SITES = [
    # Government / public services
    {"name": "USA.gov",         "url": "https://www.usa.gov",            "category": "government",  "expected": "high"},
    {"name": "IRCTC",           "url": "https://www.irctc.co.in",       "category": "government",  "expected": "medium"},
    # News
    {"name": "BBC News",        "url": "https://www.bbc.com/news",       "category": "news",        "expected": "high"},
    {"name": "NDTV",            "url": "https://www.ndtv.com",           "category": "news",        "expected": "medium"},
    # E-commerce niche
    {"name": "Etsy",            "url": "https://www.etsy.com",           "category": "ecommerce",   "expected": "medium"},
    {"name": "Meesho",          "url": "https://www.meesho.com",         "category": "ecommerce",   "expected": "low"},
    # Dev / docs
    {"name": "MDN Web Docs",    "url": "https://developer.mozilla.org",  "category": "dev-docs",    "expected": "high"},
    {"name": "Stack Overflow",  "url": "https://stackoverflow.com",      "category": "dev-docs",    "expected": "medium"},
    # Design / portfolio
    {"name": "Dribbble",        "url": "https://dribbble.com",           "category": "design",      "expected": "low"},
    {"name": "Awwwards",        "url": "https://www.awwwards.com",       "category": "design",      "expected": "low"},
]

_TIER_ORDER = {"low": 0, "medium": 1, "high": 2}


def _score_to_expected_tier(score: float) -> str:
    if score >= 85.0:
        return "high"
    if score >= 70.0:
        return "medium"
    return "low"


def _expected_alignment(expected: str, predicted: str) -> tuple[bool, int]:
    exp = str(expected).strip().lower()
    pred = str(predicted).strip().lower()
    if exp not in _TIER_ORDER or pred not in _TIER_ORDER:
        return False, 2
    distance = abs(_TIER_ORDER[pred] - _TIER_ORDER[exp])
    return distance == 0, distance


def _is_access_limited_result(result: dict, issues: list[dict]) -> bool:
    """Classify audits that are network/auth blocked or fetch-limited."""
    if bool(result.get("degraded_mode", False)) and str(result.get("degraded_reason", "")).strip().lower() == "blocked_request":
        return True
    rule_ids = {str(i.get("rule_id") or "").strip().lower() for i in issues}
    return bool({"blocked-request-partial", "fetch-unavailable"} & rule_ids)


async def audit_site(site: dict, scan_mode: str) -> dict:
    """Audit a single site and capture comprehensive telemetry."""
    start = time.time()
    try:
        result = await run_audit(
            site["url"],
            scan_mode=scan_mode,
            precision_profile="production",
            enable_enrichment=False,
            enable_cognitive=True,
            use_cache=False,
        )
        elapsed = round(time.time() - start, 2)

        issues = result.get("issues", [])
        structural_rules = {
            "landmark-roles", "no-main-landmark", "region",
            "no-nav-landmark", "no-header-landmark", "no-footer-landmark",
        }

        # Severity breakdown
        severity_counts = defaultdict(int)
        for i in issues:
            severity_counts[i.get("severity", "unknown")] += 1

        # Rule distribution
        rule_counts = defaultdict(int)
        for i in issues:
            rule_counts[i.get("rule_id", "unknown")] += 1

        top_rules = sorted(rule_counts.items(), key=lambda x: -x[1])[:8]
        structural_fp = sum(1 for i in issues if i.get("rule_id", "") in structural_rules)

        # Category distribution
        cat_counts = defaultdict(int)
        for i in issues:
            cat_counts[i.get("category", "other")] += 1

        # Confidence stats
        confidences = [i.get("confidence", 0) for i in issues]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        low_conf_count = sum(1 for c in confidences if c < 0.7)

        # Precision telemetry
        pt = result.get("precision_profile_telemetry", {})
        score_value = float(result.get("score", 0) or 0)
        access_limited = _is_access_limited_result(result, issues)
        predicted_tier = "access-limited" if access_limited else _score_to_expected_tier(score_value)
        aligned, alignment_distance = _expected_alignment(site.get("expected", ""), predicted_tier)
        alignment_applicable = not access_limited
        if not alignment_applicable:
            aligned = False
            alignment_distance = 0

        # Phase 2 Rule Tracking
        phase2_rules = {
            "meaningful-sequence", "orientation-lock", "images-of-text", "on-input-context-change",
            "captcha-detected", "readability", "jargon", "cta-clarity", 
            "nav-complexity", "form-usability", "form-no-progress", "error-message-quality"
        }
        phase2_found = {i.get("rule_id") for i in issues if i.get("rule_id") in phase2_rules}

        return {
            "name": site["name"],
            "url": site["url"],
            "category": site["category"],
            "expected_tier": site["expected"],
            "predicted_tier": predicted_tier,
            "expected_alignment": aligned,
            "expected_alignment_distance": alignment_distance,
            "alignment_applicable": alignment_applicable,
            "access_limited": access_limited,
            "scan_mode": scan_mode,
            "score": score_value,
            "total_issues": len(issues),
            "structural_fp": structural_fp,
            "severity": dict(severity_counts),
            "top_rules": [{"rule": r, "count": c} for r, c in top_rules],
            "phase2_rules_found": list(phase2_found),
            "categories": dict(cat_counts),
            "avg_confidence": round(avg_conf, 3),
            "low_confidence_count": low_conf_count,
            "scan_time_s": elapsed,
            "degraded_mode": result.get("degraded_mode", False),
            "engines_used": result.get("engines_used", []),
            "telemetry": {
                "input_issues": pt.get("input_issues", 0),
                "reported_issues": pt.get("reported_issues", 0),
                "dropped_structural": pt.get("dropped_structural", 0),
                "dropped_low_confidence": pt.get("dropped_low_confidence", 0),
                "dropped_excluded_rules": pt.get("dropped_excluded_rules", 0),
                "suppression_rate": pt.get("suppression_rate", 0),
                "suppression_warning": pt.get("suppression_warning", False),
                "low_issue_guard_active": pt.get("low_issue_guard_active", False),
            },
            "success": True,
            "error": None,
        }
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {
            "name": site["name"],
            "url": site["url"],
            "category": site["category"],
            "expected_tier": site["expected"],
            "predicted_tier": "unknown",
            "expected_alignment": False,
            "expected_alignment_distance": 2,
            "alignment_applicable": False,
            "access_limited": True,
            "scan_mode": scan_mode,
            "score": 0,
            "total_issues": 0,
            "structural_fp": 0,
            "severity": {},
            "top_rules": [],
            "categories": {},
            "avg_confidence": 0,
            "low_confidence_count": 0,
            "scan_time_s": elapsed,
            "degraded_mode": True,
            "engines_used": [],
            "telemetry": {},
            "success": False,
            "error": str(e)[:300],
        }


def print_header(title: str):
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def print_section(title: str):
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


async def main():
    print_header("BEACON Production Readiness - 10-Site Comprehensive Benchmark")
    print("  Profile: production | Modes: fast + deep")
    print(f"  Sites: {len(BENCHMARK_SITES)} | Expected audits: {len(BENCHMARK_SITES) * 2}")

    all_results = {"fast": [], "deep": []}

    for mode in ["fast", "deep"]:
        print_header(f"SCAN MODE: {mode.upper()}")

        for site in BENCHMARK_SITES:
            print(f"  [{mode:4s}] {site['name']:20s} -> ", end="", flush=True)
            result = await audit_site(site, mode)
            all_results[mode].append(result)

            status = "[OK]" if result["success"] else "[FAIL]"
            guard = " [GUARD]" if result.get("telemetry", {}).get("low_issue_guard_active") else ""
            warn = " [WARN]" if result.get("telemetry", {}).get("suppression_warning") else ""

            phase2_str = f" Phase2: {', '.join(result['phase2_rules_found'])}" if result['phase2_rules_found'] else ""
            print(
                f"{status} score={result['score']:5.1f}  "
                f"issues={result['total_issues']:3d}  "
                f"strFP={result['structural_fp']}  "
                f"time={result['scan_time_s']:.1f}s"
                f"{guard}{warn}{phase2_str}"
            )

    # ════════════════════════════════════════════════════════════
    # DETAILED RESULTS
    # ════════════════════════════════════════════════════════════

    print_header("DETAILED COMPARISON TABLE: FAST vs DEEP")
    hdr = f"{'Site':20s} | {'F.Score':>7s} {'D.Score':>7s} {'Delta':>5s} | {'F.Iss':>5s} {'D.Iss':>5s} | {'F.Time':>6s} {'D.Time':>6s} | {'Cat':>10s}"
    print(hdr)
    print("-" * len(hdr))

    for f, d in zip(all_results["fast"], all_results["deep"]):
        if not f["success"] and not d["success"]:
            print(f"{f['name']:20s} │ {'ERR':>7s} {'ERR':>7s} {'':>5s} │ {'':>5s} {'':>5s} │ {'':>6s} {'':>6s} │ {f['category']:>10s}")
            continue

        fs = f["score"] if f["success"] else 0
        ds = d["score"] if d["success"] else 0
        delta = ds - fs
        d_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"

        print(
            f"{f['name']:20s} │ "
            f"{fs:7.1f} {ds:7.1f} {d_str:>5s} │ "
            f"{f['total_issues']:5d} {d['total_issues']:5d} │ "
            f"{f['scan_time_s']:6.1f} {d['scan_time_s']:6.1f} │ "
            f"{f['category']:>10s}"
        )

    # ── Per-site deep analysis ──────────────────────────────────
    print_header("PER-SITE ANALYSIS (Production Profile)")

    for mode in ["fast", "deep"]:
        print_section(f"Mode: {mode.upper()}")
        for r in all_results[mode]:
            if not r["success"]:
                print(f"\n  [X] {r['name']}: {r['error'][:80]}")
                continue

            print(f"\n  {'-' * 50}")
            print(f"  {r['name']} ({r['url']})")
            print(f"  {'-' * 50}")
            print(f"  Score: {r['score']:.1f}/100 | Issues: {r['total_issues']} | Time: {r['scan_time_s']:.2f}s")
            if bool(r.get("alignment_applicable", True)):
                print(
                    f"  Expected: {r['expected_tier']} | Predicted: {r.get('predicted_tier', 'unknown')} "
                    f"| Alignment: {'yes' if r.get('expected_alignment') else 'no'} | Category: {r['category']}"
                )
            else:
                print(
                    f"  Expected: {r['expected_tier']} | Predicted: access-limited "
                    f"| Alignment: n/a (blocked/partial audit) | Category: {r['category']}"
                )
            print(f"  Engines: {', '.join(r['engines_used'])}")

            if r["severity"]:
                sev_str = ", ".join(f"{k}={v}" for k, v in sorted(r["severity"].items()))
                print(f"  Severity: {sev_str}")

            if r["top_rules"]:
                print("  Top rules:")
                for rule in r["top_rules"][:5]:
                    print(f"    • {rule['rule']:35s} ×{rule['count']}")

            t = r.get("telemetry", {})
            print(f"  Filtering: {t.get('input_issues', 0)} -> {t.get('reported_issues', 0)} "
                  f"(dropped: struct={t.get('dropped_structural',0)}, "
                  f"conf={t.get('dropped_low_confidence',0)}, "
                  f"excl={t.get('dropped_excluded_rules',0)})")
            print(f"  Suppression rate: {t.get('suppression_rate', 0):.1%}"
                  f" | Guard: {'🛡️ ACTIVE' if t.get('low_issue_guard_active') else 'off'}"
                  f" | Warning: {'⚠️ YES' if t.get('suppression_warning') else 'no'}")

            # Precision signal check
            if r["avg_confidence"] > 0.85 and r["total_issues"] > 0:
                print(f"  [OK] High avg confidence ({r['avg_confidence']:.2f}) -> strong precision signal")
            elif r["low_confidence_count"] > r["total_issues"] * 0.3:
                print(f"  [WARN] {r['low_confidence_count']}/{r['total_issues']} issues have low confidence -> review")

    # ── Aggregate metrics ───────────────────────────────────────
    print_header("AGGREGATE PRODUCTION READINESS METRICS")

    for mode in ["fast", "deep"]:
        results = [r for r in all_results[mode] if r["success"]]
        if not results:
            continue

        scores = [r["score"] for r in results]
        times = [r["scan_time_s"] for r in results]
        issues = [r["total_issues"] for r in results]
        warnings = sum(1 for r in results if r.get("telemetry", {}).get("suppression_warning"))
        guards = sum(1 for r in results if r.get("telemetry", {}).get("low_issue_guard_active"))
        aligned = sum(1 for r in results if bool(r.get("expected_alignment", False)))
        avg_alignment_distance = (
            sum(float(r.get("expected_alignment_distance", 2) or 0) for r in results) / len(results)
        )

        print(f"\n  {mode.upper()} MODE ({len(results)}/{len(BENCHMARK_SITES)} sites successful)")
        print(f"  |- Avg Score:        {sum(scores)/len(scores):.1f}")
        print(f"  |- Score Range:      {min(scores):.1f} - {max(scores):.1f}")
        print(f"  |- Avg Issues:       {sum(issues)/len(issues):.1f}")
        print(f"  |- Avg Scan Time:    {sum(times)/len(times):.2f}s")
        print(f"  |- P95 Scan Time:    {sorted(times)[int(len(times)*0.95)]:.2f}s")
        print(f"  |- Safeguard Warns:  {warnings}/{len(results)}")
        print(f"  |- Guard Activations:{guards}/{len(results)}")
        print(f"  |- Alignment Rate:   {aligned}/{len(results)} ({(aligned/len(results)):.0%})")
        print(f"  |- Avg Align Delta:  {avg_alignment_distance:.2f} tiers")

        # Category breakdown
        cat_scores = defaultdict(list)
        for r in results:
            cat_scores[r["category"]].append(r["score"])
        print("  |_ By Category:")
        for cat, cat_s in sorted(cat_scores.items()):
            print(f"     |- {cat:12s}: avg={sum(cat_s)/len(cat_s):.1f} ({len(cat_s)} sites)")

    # ── Production readiness verdict ────────────────────────────
    print_header("PRODUCTION READINESS VERDICT")

    fast_results = [r for r in all_results["fast"] if r["success"]]
    deep_results = [r for r in all_results["deep"] if r["success"]]

    checks = []

    # Check 1: success rate
    success_rate = (len(fast_results) + len(deep_results)) / (len(BENCHMARK_SITES) * 2)
    checks.append(("Runtime success rate", success_rate >= 0.90,
                    f"{success_rate:.0%} ({'≥90%' if success_rate >= 0.90 else '<90%'})"))

    # Check 2: no zero-score on >1-issue sites
    zero_scores = [r for r in fast_results + deep_results if r["score"] == 0 and r["success"]]
    checks.append(("No false zero scores", len(zero_scores) == 0,
                    f"{len(zero_scores)} found"))

    # Check 3: suppression safeguard
    total_warns = sum(1 for r in fast_results + deep_results
                       if r.get("telemetry", {}).get("suppression_warning"))
    checks.append(("Suppression safeguard", total_warns <= 2,
                    f"{total_warns} warnings (≤2 acceptable)"))

    # Check 4: fast mode p95 <= 3.5s (allows mild network variance)
    fast_times = sorted([r["scan_time_s"] for r in fast_results if not bool(r.get("access_limited", False))])
    p95 = fast_times[int(len(fast_times) * 0.95)] if fast_times else 0
    checks.append(("Fast mode P95 <= 3.5s", p95 <= 3.5, f"{p95:.2f}s"))

    # Check 5: deep mode p95 < 60s
    deep_times = sorted([r["scan_time_s"] for r in deep_results])
    p95d = deep_times[int(len(deep_times) * 0.95)] if deep_times else 0
    checks.append(("Deep mode P95 < 60s", p95d < 60.0, f"{p95d:.2f}s"))

    # Check 6: avg score distribution makes sense
    if fast_results:
        avg_score = sum(r["score"] for r in fast_results) / len(fast_results)
        checks.append(("Avg score 70-95 range", 70 <= avg_score <= 95,
                        f"{avg_score:.1f}"))

    # Check 7: high confidence ratio
    if fast_results:
        all_confs = [r["avg_confidence"] for r in fast_results if r["avg_confidence"] > 0]
        avg_conf = sum(all_confs) / len(all_confs) if all_confs else 0
        checks.append(("Avg confidence > 0.70", avg_conf > 0.70,
                        f"{avg_conf:.2f}"))

    # Check 8: expectation alignment
    combined_results = fast_results + deep_results
    applicable_results = [r for r in combined_results if bool(r.get("alignment_applicable", True))]
    if applicable_results:
        aligned = sum(1 for r in applicable_results if bool(r.get("expected_alignment", False)))
        alignment_rate = aligned / len(applicable_results)
        checks.append(("Expectation alignment >= 65%", alignment_rate >= 0.65,
                        f"{alignment_rate:.0%} (applicable={len(applicable_results)})"))

    all_pass = True
    advisory_checks = {"Expectation alignment >= 65%"}
    for name, passed, detail in checks:
        is_advisory = name in advisory_checks
        if passed:
            icon = "[PASS]"
        else:
            icon = "[INFO]" if is_advisory else "[FAIL]"
        print(f"  {icon} {name:35s} {detail}")
        if not passed and not is_advisory:
            all_pass = False

    print()
    if all_pass:
        print("  [SUCCESS] ALL CHECKS PASSED - Production profile is ready for rollout!")
    else:
        print("  [WARNING] Some checks failed - review before promoting to default.")

    summary_payload = {"fast": {}, "deep": {}, "overall": {}}
    for mode in ["fast", "deep"]:
        results = [r for r in all_results[mode] if r["success"]]
        if not results:
            summary_payload[mode] = {
                "successful_sites": 0,
                "avg_score": 0.0,
                "avg_scan_time_s": 0.0,
                "expectation_alignment_rate": 0.0,
                "avg_alignment_distance": 0.0,
                "suppression_warnings": 0,
            }
            continue

        applicable = [r for r in results if bool(r.get("alignment_applicable", True))]
        aligned = sum(1 for r in applicable if bool(r.get("expected_alignment", False)))
        alignment_rate = (aligned / len(applicable)) if applicable else 0.0
        avg_alignment_distance = (
            sum(float(r.get("expected_alignment_distance", 0) or 0) for r in applicable) / len(applicable)
            if applicable
            else 0.0
        )
        summary_payload[mode] = {
            "successful_sites": len(results),
            "avg_score": round(sum(float(r.get("score", 0) or 0) for r in results) / len(results), 3),
            "avg_scan_time_s": round(sum(float(r.get("scan_time_s", 0) or 0) for r in results) / len(results), 3),
            "expectation_alignment_rate": round(alignment_rate, 4),
            "avg_alignment_distance": round(avg_alignment_distance, 4),
            "alignment_applicable_sites": len(applicable),
            "access_limited_sites": sum(1 for r in results if bool(r.get("access_limited", False))),
            "suppression_warnings": sum(
                1 for r in results if bool((r.get("telemetry") or {}).get("suppression_warning", False))
            ),
        }

    combined_results = [r for mode in ["fast", "deep"] for r in all_results[mode] if r["success"]]
    combined_applicable = [r for r in combined_results if bool(r.get("alignment_applicable", True))]
    if combined_applicable:
        combined_aligned = sum(1 for r in combined_applicable if bool(r.get("expected_alignment", False)))
        summary_payload["overall"] = {
            "successful_audits": len(combined_results),
            "alignment_applicable_audits": len(combined_applicable),
            "access_limited_audits": sum(1 for r in combined_results if bool(r.get("access_limited", False))),
            "expectation_alignment_rate": round(combined_aligned / len(combined_applicable), 4),
            "avg_alignment_distance": round(
                sum(float(r.get("expected_alignment_distance", 0) or 0) for r in combined_applicable) / len(combined_applicable),
                4,
            ),
        }
    else:
        summary_payload["overall"] = {
            "successful_audits": 0,
            "expectation_alignment_rate": 0.0,
            "avg_alignment_distance": 0.0,
        }

    # ── Save full results ───────────────────────────────────────
    out_path = Path("evaluation/production_benchmark_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output_payload = {
        "fast": all_results["fast"],
        "deep": all_results["deep"],
        "summary": summary_payload,
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, default=str)
    print(f"\n  Full results saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
