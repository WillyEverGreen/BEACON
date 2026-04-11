"""
Real-world 10-site benchmark for production readiness validation.

Compares 'balanced' profile (baseline) vs 'production' profile (new)
across 10 diverse sites covering different accessibility quality tiers.

Reports: per-site scores, issue counts, scan times, structural FP impact,
and aggregate precision/recall deltas.
"""
import asyncio
import json
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from app.services.audit_runner import run_audit


# 10 diverse sites: gold → medium → poor accessibility
BENCHMARK_SITES = [
    {"name": "Apple",           "url": "https://www.apple.com",        "tier": "gold"},
    {"name": "GOV.UK",          "url": "https://www.gov.uk",           "tier": "gold"},
    {"name": "Wikipedia",       "url": "https://en.wikipedia.org",     "tier": "gold"},
    {"name": "BBC",             "url": "https://www.bbc.com",          "tier": "high"},
    {"name": "GitHub",          "url": "https://github.com",           "tier": "high"},
    {"name": "MDN Web Docs",    "url": "https://developer.mozilla.org","tier": "high"},
    {"name": "Stack Overflow",  "url": "https://stackoverflow.com",    "tier": "medium"},
    {"name": "Reddit",          "url": "https://www.reddit.com",       "tier": "medium"},
    {"name": "Amazon",          "url": "https://www.amazon.com",       "tier": "complex"},
    {"name": "YouTube",         "url": "https://www.youtube.com",      "tier": "complex"},
]


async def audit_site(site: dict, profile: str) -> dict:
    """Audit a single site with the given profile and capture timing."""
    start = time.time()
    try:
        result = await run_audit(
            site["url"],
            scan_mode="fast",
            precision_profile=profile,
            enable_enrichment=False,
            enable_cognitive=False,
            use_cache=False,
        )
        elapsed = round(time.time() - start, 2)

        issues = result.get("issues", [])
        rule_ids = [i.get("rule_id", "") for i in issues]
        structural_rules = {
            "landmark-roles", "no-main-landmark", "region",
            "no-nav-landmark", "no-header-landmark", "no-footer-landmark",
        }
        structural_count = sum(1 for r in rule_ids if r in structural_rules)
        structural_rules_found = sorted({r for r in rule_ids if r in structural_rules})

        severity_breakdown = {}
        for issue in issues:
            sev = issue.get("severity", "unknown")
            severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1

        precision_telemetry = result.get("precision_profile_telemetry", {})

        return {
            "name": site["name"],
            "url": site["url"],
            "tier": site["tier"],
            "profile": profile,
            "score": result.get("score", 0.0),
            "total_issues": len(issues),
            "structural_fp_count": structural_count,
            "structural_rules_found": structural_rules_found,
            "severity_breakdown": severity_breakdown,
            "scan_time_seconds": elapsed,
            "degraded_mode": result.get("degraded_mode", False),
            "engines_used": result.get("engines_used", []),
            "top_rules": sorted(set(rule_ids))[:10],
            "dropped_structural": precision_telemetry.get("dropped_structural", 0),
            "suppression_rate": precision_telemetry.get("suppression_rate", 0.0),
            "suppression_warning": precision_telemetry.get("suppression_warning", False),
            "success": True,
            "error": None,
        }
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {
            "name": site["name"],
            "url": site["url"],
            "tier": site["tier"],
            "profile": profile,
            "score": 0.0,
            "total_issues": 0,
            "structural_fp_count": 0,
            "structural_rules_found": [],
            "severity_breakdown": {},
            "scan_time_seconds": elapsed,
            "degraded_mode": True,
            "engines_used": [],
            "top_rules": [],
            "dropped_structural": 0,
            "suppression_rate": 0.0,
            "suppression_warning": False,
            "success": False,
            "error": str(e)[:200],
        }


async def run_benchmark():
    """Run all 10 sites with both profiles and produce comparison report."""
    print("=" * 70)
    print("BEACON Production Readiness — 10-Site Real-World Benchmark")
    print("=" * 70)

    results = {"balanced": [], "production": []}

    for profile in ["balanced", "production"]:
        print(f"\n{'─' * 50}")
        print(f"Profile: {profile}")
        print(f"{'─' * 50}")

        for site in BENCHMARK_SITES:
            print(f"  Auditing {site['name']:20s} ({site['url']})...", end=" ", flush=True)
            result = await audit_site(site, profile)
            results[profile].append(result)

            status = "✅" if result["success"] else "❌"
            print(
                f"{status} score={result['score']:5.1f}  "
                f"issues={result['total_issues']:3d}  "
                f"structural_fp={result['structural_fp_count']}  "
                f"time={result['scan_time_seconds']:.1f}s"
            )

    # ── Comparison Report ───────────────────────────────────────
    print("\n" + "=" * 70)
    print("COMPARISON: balanced → production")
    print("=" * 70)

    header = f"{'Site':20s} │ {'B.Score':>7s} {'P.Score':>7s} {'Δ':>5s} │ {'B.Issues':>8s} {'P.Issues':>8s} │ {'B.StrFP':>7s} {'P.StrFP':>7s} │ {'B.Time':>6s} {'P.Time':>6s}"
    print(header)
    print("─" * len(header))

    total_b_score = total_p_score = 0
    total_b_issues = total_p_issues = 0
    total_b_struct = total_p_struct = 0
    total_b_time = total_p_time = 0
    valid_sites = 0

    for b, p in zip(results["balanced"], results["production"]):
        if not b["success"] or not p["success"]:
            print(f"{b['name']:20s} │ {'SKIP':>7s} {'SKIP':>7s} {'':>5s} │ {'':>8s} {'':>8s} │ {'':>7s} {'':>7s} │ {'':>6s} {'':>6s}")
            continue

        valid_sites += 1
        delta = p["score"] - b["score"]
        delta_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"

        print(
            f"{b['name']:20s} │ "
            f"{b['score']:7.1f} {p['score']:7.1f} {delta_str:>5s} │ "
            f"{b['total_issues']:8d} {p['total_issues']:8d} │ "
            f"{b['structural_fp_count']:7d} {p['structural_fp_count']:7d} │ "
            f"{b['scan_time_seconds']:6.1f} {p['scan_time_seconds']:6.1f}"
        )

        total_b_score += b["score"]
        total_p_score += p["score"]
        total_b_issues += b["total_issues"]
        total_p_issues += p["total_issues"]
        total_b_struct += b["structural_fp_count"]
        total_p_struct += p["structural_fp_count"]
        total_b_time += b["scan_time_seconds"]
        total_p_time += p["scan_time_seconds"]

    if valid_sites > 0:
        print("─" * len(header))
        avg_b_score = total_b_score / valid_sites
        avg_p_score = total_p_score / valid_sites
        avg_delta = avg_p_score - avg_b_score
        delta_str = f"+{avg_delta:.1f}" if avg_delta >= 0 else f"{avg_delta:.1f}"

        print(
            f"{'AVERAGE':20s} │ "
            f"{avg_b_score:7.1f} {avg_p_score:7.1f} {delta_str:>5s} │ "
            f"{total_b_issues/valid_sites:8.1f} {total_p_issues/valid_sites:8.1f} │ "
            f"{total_b_struct/valid_sites:7.1f} {total_p_struct/valid_sites:7.1f} │ "
            f"{total_b_time/valid_sites:6.1f} {total_p_time/valid_sites:6.1f}"
        )

    # ── Aggregate Metrics ───────────────────────────────────────
    print("\n" + "=" * 70)
    print("AGGREGATE METRICS")
    print("=" * 70)

    b_times = [r["scan_time_seconds"] for r in results["balanced"] if r["success"]]
    p_times = [r["scan_time_seconds"] for r in results["production"] if r["success"]]

    if b_times and p_times:
        b_times_sorted = sorted(b_times)
        p_times_sorted = sorted(p_times)
        b_p95 = b_times_sorted[int(len(b_times_sorted) * 0.95)] if len(b_times_sorted) > 1 else b_times_sorted[-1]
        p_p95 = p_times_sorted[int(len(p_times_sorted) * 0.95)] if len(p_times_sorted) > 1 else p_times_sorted[-1]

        print(f"  Avg scan time:   balanced={sum(b_times)/len(b_times):.2f}s  production={sum(p_times)/len(p_times):.2f}s")
        print(f"  P95 scan time:   balanced={b_p95:.2f}s  production={p_p95:.2f}s")
        print(f"  Total structural FP:  balanced={total_b_struct}  production={total_p_struct}")

        if total_b_struct > 0:
            reduction_pct = ((total_b_struct - total_p_struct) / total_b_struct) * 100
            print(f"  Structural FP reduction: {reduction_pct:.0f}%")

    # ── Suppression Analysis ───────────────────────────────────
    print("\n" + "=" * 70)
    print("SUPPRESSION ANALYSIS (production profile)")
    print("=" * 70)
    for r in results["production"]:
        if r["success"]:
            warning = " ⚠️ SAFEGUARD" if r["suppression_warning"] else ""
            print(
                f"  {r['name']:20s}  "
                f"dropped_structural={r['dropped_structural']:2d}  "
                f"suppression_rate={r['suppression_rate']:.1%}"
                f"{warning}"
            )

    # ── Rollout Decision ───────────────────────────────────────
    print("\n" + "=" * 70)
    print("ROLLOUT DECISION")
    print("=" * 70)

    if valid_sites > 0:
        avg_delta = (total_p_score - total_b_score) / valid_sites
        struct_reduction = total_b_struct - total_p_struct
        perf_delta = (total_p_time - total_b_time) / valid_sites
        any_warning = any(r["suppression_warning"] for r in results["production"])

        if avg_delta >= 0 and struct_reduction >= 0 and abs(perf_delta) < 2.0 and not any_warning:
            print("  ✅ SHIP: Score stable/improved, structural FP reduced, no perf regression")
        elif avg_delta < -5:
            print("  ❌ ROLLBACK: Score degradation too large")
        elif any_warning:
            print("  ⚠️ TUNE: Suppression safeguard triggered — review structural policy")
        else:
            print("  ⚠️ REVIEW: Mixed results — manual review recommended")

    # Save full results
    out_path = Path("evaluation/10site_benchmark_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Full results saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
