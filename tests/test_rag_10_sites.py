#!/usr/bin/env python3
"""
10-Site RAG Verification Test
Tests RAG enrichment effectiveness on strategic sites
"""

import asyncio
import sys
import os
import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Add app to path
sys.path.insert(0, os.path.abspath("."))

from app.services.audit_runner import run_audit


@dataclass
class SiteTest:
    url: str
    name: str
    category: str
    purpose: str
    
    
STRATEGIC_SITES = [
    SiteTest("https://www.apple.com/", "Apple", "tech", "Near-perfect accessibility baseline"),
    SiteTest("https://www.wikipedia.org/", "Wikipedia", "education", "Rich semantic HTML"),
    SiteTest("https://twitter.com/", "Twitter/X", "social", "Complex SPA with dynamic content"),
    SiteTest("https://www.gov.uk/", "GOV.UK", "government", "Gold standard accessibility"),
    SiteTest("https://www.amazon.com/", "Amazon", "ecommerce", "Complex, ad-heavy, mixed accessibility"),
    SiteTest("https://www.reddit.com/", "Reddit", "social", "SPA with infinite scroll"),
    SiteTest("https://www.nytimes.com/", "NY Times", "news", "Paywalls and overlays"),
    SiteTest("https://www.craigslist.org/", "Craigslist", "blog", "Old-school HTML"),
    SiteTest("https://web.dev/", "web.dev", "tech", "Google's accessibility site"),
    SiteTest("https://www.facebook.com/", "Facebook", "social", "Heavily obfuscated SPA"),
]


def _count_enriched_issues(issues: list[dict]) -> int:
    """Count issues with non-pending enrichment source or explicit rag_context."""
    enriched = 0
    for issue in issues:
        source = str(issue.get("_enrichment_source") or issue.get("enrichment_source") or "").strip().lower()
        if issue.get("rag_context"):
            enriched += 1
            continue
        if source and source not in {"pending", "off", "none", "unknown"}:
            enriched += 1
    return enriched


async def test_site_with_rag(site: SiteTest):
    """Test a single site with RAG enabled"""
    print(f"\n{'='*80}")
    print(f"  🎯 {site.name}")
    print(f"{'='*80}")
    print(f"  Purpose: {site.purpose}")
    print(f"  Category: {site.category}")
    print(f"{'-'*80}")
    
    # Test WITHOUT RAG (baseline)
    print(f"  [1/2] BASELINE (No RAG, No Cognitive)...")
    start = time.time()

    result_no_rag = await run_audit(
        url=site.url,
        scan_mode="deep",
        precision_profile="balanced",
        enable_enrichment=False,
        max_enrich_issues=0,
        enable_cognitive=False,
        await_enrichment=False,
    )
    time_no_rag = time.time() - start

    score_no_rag = float(result_no_rag.get("score", 0))
    issues_no_rag = int(result_no_rag.get("total_issues", 0))
    rag_enriched_no = _count_enriched_issues(result_no_rag.get("issues", []))
    
    print(f"    ✓ Score: {score_no_rag:.1f}/100")
    print(f"    ✓ Issues: {issues_no_rag}")
    print(f"    ✓ Time: {time_no_rag:.1f}s")
    print(f"    ✓ RAG enriched: {rag_enriched_no} issues")
    
    # Test WITH RAG
    print(f"  [2/2] RAG-ENABLED (With RAG, No Cognitive)...")
    start = time.time()

    result_with_rag = await run_audit(
        url=site.url,
        scan_mode="deep",
        precision_profile="balanced",
        enable_enrichment=True,
        max_enrich_issues=20,
        enable_cognitive=False,
        await_enrichment=True,
    )
    time_with_rag = time.time() - start

    score_with_rag = float(result_with_rag.get("score", 0))
    issues_with_rag = int(result_with_rag.get("total_issues", 0))
    rag_enriched_yes = _count_enriched_issues(result_with_rag.get("issues", []))
    with_rag_status = str(result_with_rag.get("enrichment_status", "unknown"))
    
    print(f"    ✓ Score: {score_with_rag:.1f}/100")
    print(f"    ✓ Issues: {issues_with_rag}")
    print(f"    ✓ Time: {time_with_rag:.1f}s")
    print(f"    ✓ RAG enriched: {rag_enriched_yes} issues")
    print(f"    ✓ Enrichment status: {with_rag_status}")
    
    # Analysis
    print(f"\n  📊 RAG Impact Analysis:")
    score_diff = score_with_rag - score_no_rag
    issues_diff = issues_with_rag - issues_no_rag
    enrichment_added = rag_enriched_yes - rag_enriched_no
    time_overhead = time_with_rag - time_no_rag
    
    print(f"    {'📈' if score_diff >= 0 else '📉'} Score: {score_diff:+.1f} points")
    print(f"    🔍 Issues: {issues_diff:+} ({'+' if issues_diff >= 0 else ''}{issues_diff})")
    print(f"    📚 Enrichment: +{enrichment_added} issues with knowledge")
    print(f"    ⏱️  Time overhead: {time_overhead:+.1f}s")
    
    if enrichment_added > 0:
        print(f"    ✅ RAG WORKING! {enrichment_added} issues enriched")
    else:
        print(f"    ❌ RAG NOT WORKING - 0 enrichments")
    
    return {
        "site": site.name,
        "url": site.url,
        "category": site.category,
        "baseline": {
            "score": score_no_rag,
            "issues": issues_no_rag,
            "rag_enriched": rag_enriched_no,
            "time": time_no_rag
        },
        "with_rag": {
            "score": score_with_rag,
            "issues": issues_with_rag,
            "rag_enriched": rag_enriched_yes,
            "time": time_with_rag,
            "enrichment_status": with_rag_status,
        },
        "impact": {
            "score_delta": score_diff,
            "issues_delta": issues_diff,
            "enrichment_added": enrichment_added,
            "time_overhead": time_overhead,
            "rag_working": enrichment_added > 0
        }
    }


async def main():
    print("="*80)
    print("  🧪 10-SITE RAG VERIFICATION TEST")
    print("="*80)
    print(f"  Testing RAG enrichment effectiveness")
    print(f"  Mode: Deep scan, No Cognitive (cost savings)")
    print("="*80)
    
    start_time = time.time()
    results = []
    
    for site in STRATEGIC_SITES:
        try:
            result = await test_site_with_rag(site)
            results.append(result)
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            results.append({
                "site": site.name,
                "error": str(e)
            })
    
    total_time = time.time() - start_time
    
    # Summary
    print(f"\n\n{'='*80}")
    print(f"  📊 RAG VERIFICATION SUMMARY")
    print(f"{'='*80}")
    
    successful = [r for r in results if "error" not in r]
    rag_working_count = sum(1 for r in successful if r["impact"]["rag_working"])
    
    print(f"\n📋 Execution Summary:")
    print(f"  Total sites: {len(STRATEGIC_SITES)}")
    print(f"  Successful: {len(successful)}")
    print(f"  RAG working: {rag_working_count}/{len(successful)} ({rag_working_count/len(successful)*100:.1f}%)")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    
    if successful:
        avg_enrichment = sum(r["impact"]["enrichment_added"] for r in successful) / len(successful)
        total_enriched = sum(r["impact"]["enrichment_added"] for r in successful)
        
        print(f"\n📚 RAG Enrichment:")
        print(f"  Total enriched issues: {total_enriched}")
        print(f"  Average enrichment/site: {avg_enrichment:.1f} issues")
        
        print(f"\n⏱️  Performance:")
        avg_overhead = sum(r["impact"]["time_overhead"] for r in successful) / len(successful)
        print(f"  Average RAG overhead: {avg_overhead:.1f}s")
        
        print(f"\n📊 Site-by-Site Results:")
        print(f"  {'Site':<15} {'Baseline':<10} {'With RAG':<10} {'Enriched':<10} {'Status':<10}")
        print(f"  {'-'*60}")
        for r in successful:
            status = "✅ WORKS" if r["impact"]["rag_working"] else "❌ FAIL"
            print(f"  {r['site']:<15} "
                  f"{r['baseline']['rag_enriched']:>3} issues  "
                  f"{r['with_rag']['rag_enriched']:>3} issues  "
                  f"+{r['impact']['enrichment_added']:>2} issues   "
                  f"{status}")
    
    # Save results
    output_file = Path("tests/rag_10_site_results.json")
    output_file.write_text(json.dumps(results, indent=2))
    print(f"\n💾 Results saved to: {output_file}")
    
    # Final verdict
    print(f"\n{'='*80}")
    print(f"  🏆 FINAL VERDICT")
    print(f"{'='*80}")
    if rag_working_count > 7:  # >70% success rate
        print(f"  ✅ RAG IS WORKING: {rag_working_count}/{len(successful)} sites enriched")
    elif rag_working_count > 0:
        print(f"  ⚠️  RAG PARTIALLY WORKING: {rag_working_count}/{len(successful)} sites")
        print(f"      Check ChromaDB collection and knowledge base")
    else:
        print(f"  ❌ RAG NOT WORKING: 0 sites enriched")
        print(f"      Run: python run_ingestion.py to populate knowledge base")
    
    print(f"{'='*80}")
    print(f"  ✅ RAG VERIFICATION COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
