"""
BEACON Engine Stress Test Harness
=================================
Tests the engine against real-world sites across 5 tiers:
- Tier 1: W3C WAI Before/After Demo (known violations)
- Tier 2: Intentionally broken test sites
- Tier 3: Real-world sites (worst WebAIM categories)
- Tier 4: Clean/accessible sites (false-positive check)
- Tier 5: Industry-specific stress tests

Validates: detection, confidence, prioritization, degraded mode, cache correctness.
"""
import asyncio
import json
import sys
import time
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.audit_runner import run_audit
from app.config import CACHE_STATS


# ── Test URLs by Tier ─────────────────────────────────────────────
TEST_URLS = {
    "tier1_known_violations": [
        ("W3C BAD Demo (Before)", "https://www.w3.org/WAI/demos/bad/before/home.html"),
    ],
    "tier2_intentionally_broken": [
        ("Accessibility Fails", "https://aduggin.github.io/accessibility-fails/"),
    ],
    "tier3_real_world_worst": [
        ("YouTube (media-heavy)", "https://www.youtube.com"),
        ("Amazon (e-commerce)", "https://www.amazon.com"),
    ],
    "tier4_clean_sites_fp_check": [
        ("GOV.UK (gold standard)", "https://www.gov.uk"),
        ("W3C WAI (should be clean)", "https://www.w3.org/WAI/"),
    ],
    "tier5_industry_stress": [
        ("GitHub (SaaS dashboard)", "https://github.com"),
        ("Wikipedia (content-heavy)", "https://en.wikipedia.org"),
    ],
}


def format_result(name: str, result: dict) -> dict:
    """Extract the key metrics from an audit result."""
    return {
        "name": name,
        "score": result.get("score", 0),
        "total_issues": result.get("total_issues", 0),
        "scan_mode": result.get("scan_mode", ""),
        "scan_time": result.get("scan_time_seconds", 0),
        "engines_used": result.get("engines_used", []),
        "degraded_mode": result.get("degraded_mode", False),
        "skipped_components": result.get("skipped_components", []),
        "degradation_reason": result.get("degradation_reason"),
        "cognitive_mode": result.get("cognitive_mode", "off"),
        "expected_score_after_fix": result.get("expected_score_after_fix", 0),
        "score_improvement": result.get("score_improvement", 0),
        "priority_ranking": [
            {"rank": p.get("rank"), "rule_id": p.get("rule_id"), "score": p.get("total_score"), "count": p.get("affected_count")}
            for p in result.get("priority_ranking", [])
        ],
        "severity_breakdown": {},
        "confidence_stats": {},
        "sample_confidence_reasons": [],
        "sample_impact_summaries": [],
    }


def enrich_stats(summary: dict, issues: list[dict]):
    """Add severity breakdown, confidence stats, and sample explanations."""
    # Severity breakdown
    sev_counts = {}
    for i in issues:
        sev = i.get("severity", "unknown")
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
    summary["severity_breakdown"] = sev_counts

    # Confidence stats
    if issues:
        confs = [i.get("confidence", 0) for i in issues]
        summary["confidence_stats"] = {
            "avg": round(sum(confs) / len(confs), 3),
            "min": round(min(confs), 3),
            "max": round(max(confs), 3),
            "needs_review_count": sum(1 for i in issues if i.get("needs_manual_review")),
        }

    # Sample confidence reasons (first 3)
    reasons = [i.get("confidence_reason", "") for i in issues if i.get("confidence_reason")]
    summary["sample_confidence_reasons"] = reasons[:3]

    # Sample impact summaries (first 3 unique)
    seen = set()
    for i in issues:
        s = i.get("impact_summary", "")
        if s and s not in seen:
            seen.add(s)
            summary["sample_impact_summaries"].append(s)
            if len(summary["sample_impact_summaries"]) >= 3:
                break


async def run_test_tier(tier_name: str, urls: list[tuple], scan_mode: str = "fast") -> list[dict]:
    """Run audits for a tier and return summaries."""
    print(f"\n{'='*60}")
    print(f"  TIER: {tier_name} (mode={scan_mode})")
    print(f"{'='*60}")

    results = []
    for name, url in urls:
        print(f"\n  → Auditing: {name} ({url})")
        try:
            start = time.time()
            result = await run_audit(url=url, scan_mode=scan_mode, precision_profile="balanced")
            elapsed = time.time() - start

            summary = format_result(name, result)
            enrich_stats(summary, result.get("issues", []))

            print(f"    Score: {summary['score']}/100 | Issues: {summary['total_issues']} | Time: {elapsed:.1f}s")
            print(f"    Degraded: {summary['degraded_mode']} | Engines: {summary['engines_used']}")
            if summary["priority_ranking"]:
                top = summary["priority_ranking"][0]
                print(f"    Top fix: {top['rule_id']} (score={top['score']}, count={top['count']})")
            if summary["confidence_stats"]:
                cs = summary["confidence_stats"]
                print(f"    Confidence: avg={cs['avg']}, min={cs['min']}, max={cs['max']}, needs_review={cs['needs_review_count']}")
            if summary["sample_confidence_reasons"]:
                print(f"    Reason: {summary['sample_confidence_reasons'][0][:80]}...")
            if summary["sample_impact_summaries"]:
                print(f"    Impact: {summary['sample_impact_summaries'][0][:80]}...")

            results.append(summary)
        except Exception as e:
            print(f"    ❌ FAILED: {e}")
            results.append({"name": name, "error": str(e)})

    return results


async def test_cache_correctness():
    """Verify cache invalidation works: same URL, different modes should not collide."""
    print(f"\n{'='*60}")
    print(f"  CACHE CORRECTNESS TEST")
    print(f"{'='*60}")

    url = "https://www.w3.org/WAI/"

    # Reset stats
    for k in CACHE_STATS:
        CACHE_STATS[k] = 0

    # First run — should be a miss
    r1 = await run_audit(url=url, scan_mode="fast", precision_profile="balanced")
    print(f"  Run 1 (fast): score={r1['score']}, cache_hit={r1.get('cache_hit', False)}")

    # Second run — same URL, same mode — should be a HIT
    r2 = await run_audit(url=url, scan_mode="fast", precision_profile="balanced")
    print(f"  Run 2 (fast): score={r2['score']}, cache_hit={r2.get('cache_hit', False)}")

    # Third run — same URL, DIFFERENT mode — should be a MISS (different cache key)
    r3 = await run_audit(url=url, scan_mode="minimal", precision_profile="balanced")
    print(f"  Run 3 (minimal): score={r3['score']}, cache_hit={r3.get('cache_hit', False)}")

    print(f"\n  Cache Stats: {json.dumps(CACHE_STATS, indent=2)}")

    # Assertions
    if r2.get("cache_hit"):
        print("  ✅ PASS: Same URL+mode hit cache correctly")
    else:
        print("  ⚠️  WARN: Cache miss on repeated URL (may be TTL or first run)")

    if r1["score"] == r2["score"]:
        print("  ✅ PASS: Cached result is identical to fresh result")
    else:
        print(f"  ❌ FAIL: Score mismatch: fresh={r1['score']} vs cached={r2['score']}")


async def main():
    print("=" * 60)
    print("  BEACON Engine Stress Test Harness")
    print("  Testing against real-world accessibility targets")
    print("=" * 60)

    all_results = {}
    total_start = time.time()

    # Run each tier
    for tier_name, urls in TEST_URLS.items():
        tier_results = await run_test_tier(tier_name, urls, scan_mode="fast")
        all_results[tier_name] = tier_results

    # Cache test
    await test_cache_correctness()

    total_time = time.time() - total_start

    # ── Summary ────────────────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*60}")

    total_sites = 0
    total_issues = 0
    total_errors = 0
    for tier, results in all_results.items():
        for r in results:
            total_sites += 1
            if "error" in r:
                total_errors += 1
            else:
                total_issues += r.get("total_issues", 0)

    print(f"  Sites tested: {total_sites}")
    print(f"  Total issues found: {total_issues}")
    print(f"  Errors: {total_errors}")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Cache stats: {json.dumps(CACHE_STATS)}")

    # Validation checks
    print(f"\n  VALIDATION:")

    # Check 1: Known-bad sites should have issues
    for r in all_results.get("tier1_known_violations", []):
        if not r.get("error") and r.get("total_issues", 0) > 0:
            print(f"  ✅ {r['name']}: {r['total_issues']} issues found (expected > 0)")
        elif not r.get("error"):
            print(f"  ❌ {r['name']}: 0 issues on a known-bad site!")

    # Check 2: Clean sites should have fewer issues
    for r in all_results.get("tier4_clean_sites_fp_check", []):
        if not r.get("error"):
            status = "✅" if r.get("total_issues", 999) < 30 else "⚠️ "
            print(f"  {status} {r['name']}: {r.get('total_issues', '?')} issues (expected low FP rate)")

    # Check 3: All sites should have confidence_reason populated
    has_reasons = True
    for tier, results in all_results.items():
        for r in results:
            if not r.get("error") and not r.get("sample_confidence_reasons"):
                has_reasons = False
    print(f"  {'✅' if has_reasons else '❌'} Confidence reasons populated on all audits")

    # Check 4: All sites should have impact_summary
    has_impact = True
    for tier, results in all_results.items():
        for r in results:
            if not r.get("error") and not r.get("sample_impact_summaries"):
                has_impact = False
    print(f"  {'✅' if has_impact else '❌'} Impact summaries populated on all audits")

    # Save full results
    output_path = os.path.join(os.path.dirname(__file__), "test_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Full results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
