"""
BEACON Engine v2 — Real-Site Test Suite
Tests sugarlabs.org AGAIN (to show improvement) and wikipedia.org (new site).
Runs both fast and deep scans.
"""
import asyncio
import json
import sys
from datetime import datetime

async def run_test(url: str, label: str, mode: str = "deep") -> dict:
    """Run audit and return results summary."""
    from app.services.audit_runner import run_audit
    print(f"\n{'='*60}")
    print(f"  {label} | {url} | mode={mode}")
    print(f"{'='*60}")
    result = await run_audit(url, scan_mode=mode, precision_profile="balanced", enable_enrichment=False)
    score = result.get("score", 0)
    total = result.get("total_issues", 0)
    duration = result.get("scan_time_seconds", 0)
    scs = result.get("wcag_scs_covered", [])
    issues = result.get("issues", [])

    # Count grouped issues
    grouped = sum(1 for i in issues if i.get("is_grouped"))
    by_severity = {}
    for i in issues:
        s = i.get("severity", "unknown")
        by_severity[s] = by_severity.get(s, 0) + 1

    # Count rule IDs
    rule_ids = set(i.get("rule_id") for i in issues)

    print(f"  Score:         {score}/100")
    print(f"  Total issues:  {total}")
    print(f"  Grouped axe:   {grouped}")
    print(f"  Scan time:     {duration:.2f}s")
    print(f"  WCAG SCs:      {len(scs)} ({', '.join(sorted(scs)[:8])}...)")
    print(f"  Severity:      {by_severity}")
    print(f"  Rule IDs ({len(rule_ids)}): {', '.join(sorted(rule_ids)[:12])}...")

    return {
        "label": label,
        "url": url,
        "mode": mode,
        "score": score,
        "total_issues": total,
        "grouped_axe_issues": grouped,
        "scan_time_seconds": round(duration, 2),
        "wcag_scs_covered": len(scs),
        "wcag_scs": scs,
        "severity_breakdown": by_severity,
        "unique_rule_ids": len(rule_ids),
        "rule_ids": list(rule_ids),
    }

async def main():
    results = []

    # 1. Sugarlabs re-test (should be much improved)
    r = await run_test("https://www.sugarlabs.org/", "SugarLabs [Re-test]", mode="deep")
    results.append(r)

    # Give a moment between requests
    await asyncio.sleep(2)

    # 2. Wikipedia (new site — well-known, comprehensive)
    r2 = await run_test("https://en.wikipedia.org/wiki/Web_accessibility", "Wikipedia [New]", mode="deep")
    results.append(r2)

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = f"beacon_v2_test_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n\nResults saved to {out_file}")

    # Summary table
    print("\n" + "="*60)
    print("BEACON v2 COMPARISON SUMMARY")
    print("="*60)
    print(f"{'Site':<25} {'Score':>6} {'Issues':>8} {'Grpd':>6} {'WCAG SCs':>9} {'Rules':>7}")
    print("-"*60)
    for r in results:
        print(f"{r['label']:<25} {r['score']:>6}/100 {r['total_issues']:>6} {r['grouped_axe_issues']:>6} {r['wcag_scs_covered']:>7} SCs {r['unique_rule_ids']:>5}")
    print("="*60)

    print("\n✅ BEFORE vs AFTER (sugarlabs.org deep scan):")
    print("  BEFORE: score=0/100, issues=355 (325 region violations = 91%% noise)")
    print(f"  AFTER:  score={results[0]['score']}/100, issues={results[0]['total_issues']}")

asyncio.run(main())
