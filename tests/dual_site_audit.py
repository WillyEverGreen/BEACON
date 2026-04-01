"""Quick audit of sugarlabs + mozilla."""
import asyncio
from collections import Counter
from app.services.audit_runner import run_audit


async def test_site(url, label):
    result = await run_audit(
        url, scan_mode="deep",
        precision_profile="balanced",
        enable_enrichment=False
    )
    issues = result.get("issues", [])
    scs = result.get("wcag_scs_covered", [])
    grouped = [i for i in issues if i.get("is_grouped")]
    rule_counts = Counter(i.get("rule_id") for i in issues)
    sev_counts = Counter(i.get("severity") for i in issues)

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  URL: {url}")
    print(f"{'='*60}")
    print(f"  Score:          {result.get('score')}/100")
    print(f"  Total issues:   {result.get('total_issues')}")
    print(f"  Grouped axe:    {len(grouped)}")
    print(f"  Scan time:      {result.get('scan_time_seconds', 0):.2f}s")
    print(f"  WCAG SCs:       {len(scs)}: {sorted(scs)}")
    print(f"  Severity:       {dict(sev_counts)}")
    print(f"  Top rules:")
    for rule, count in rule_counts.most_common(10):
        print(f"    [{count}] {rule}")
    print(f"  Grouped details:")
    for i in grouped:
        print(f"    {i.get('rule_id')}: {i.get('evidence', {}).get('affected_count', '?')} affected")
    return result


async def main():
    await test_site("https://www.sugarlabs.org/", "SugarLabs v2 [RE-TEST]")
    await asyncio.sleep(1)
    await test_site("https://www.mozilla.org/en-US/", "Mozilla.org [NEW SITE]")
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
