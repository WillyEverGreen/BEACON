#!/usr/bin/env python3
"""
RAG vs No-RAG Comparative Benchmark - 100 Sites
================================================
Tests the same 100 sites as the baseline benchmark with TWO configurations:

1. **Baseline (No RAG, No Cognitive)**: Pure engine accuracy
2. **RAG-Enhanced (RAG enabled, No Cognitive)**: Knowledge-enriched results

This isolates the impact of your RAG knowledge base on audit quality.

Expected improvements with RAG:
- More contextual remediation suggestions
- Better categorization of issues
- Enhanced educational content
- Domain-specific best practices
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.audit_runner import run_audit

# Same 100 sites as the original benchmark for direct comparison
TEST_SITES = [
    # === ACCESSIBILITY LEADERS (10) ===
    ("https://www.a11yproject.com/", "A11y Project", "accessibility"),
    ("https://webaim.org/", "WebAIM", "accessibility"),
    ("https://www.w3.org/WAI/", "W3C WAI", "accessibility"),
    ("https://www.deque.com/", "Deque", "accessibility"),
    ("https://inclusivedesignprinciples.org/", "Inclusive Design", "accessibility"),
    ("https://www.section508.gov/", "Section508.gov", "accessibility"),
    ("https://www.digital.govt.nz/standards/", "NZ Digital Standards", "accessibility"),
    ("https://accessibility.blog.gov.uk/", "UK A11y Blog", "accessibility"),
    ("https://www.levelaccess.com/", "Level Access", "accessibility"),
    ("https://wave.webaim.org/", "WAVE Tool", "accessibility"),
    
    # === GOVERNMENT (10) ===
    ("https://www.usa.gov/", "USA.gov", "government"),
    ("https://www.gov.uk/", "GOV.UK", "government"),
    ("https://www.canada.ca/en.html", "Canada.ca", "government"),
    ("https://www.nhs.uk/", "NHS UK", "government"),
    ("https://www.australia.gov.au/", "Australia.gov", "government"),
    ("https://digital.gov/", "Digital.gov", "government"),
    ("https://www.whitehouse.gov/", "White House", "government"),
    ("https://www.irs.gov/", "IRS", "government"),
    ("https://www.ssa.gov/", "Social Security", "government"),
    ("https://www.state.gov/", "State Department", "government"),
    
    # === TECH GIANTS (15) ===
    ("https://www.microsoft.com/", "Microsoft", "tech"),
    ("https://www.apple.com/", "Apple", "tech"),
    ("https://www.google.com/", "Google", "tech"),
    ("https://github.com/", "GitHub", "tech"),
    ("https://about.meta.com/", "Meta", "tech"),
    ("https://www.amazon.com/", "Amazon", "tech"),
    ("https://www.netflix.com/", "Netflix", "tech"),
    ("https://www.adobe.com/", "Adobe", "tech"),
    ("https://www.salesforce.com/", "Salesforce", "tech"),
    ("https://www.oracle.com/", "Oracle", "tech"),
    ("https://www.ibm.com/", "IBM", "tech"),
    ("https://www.intel.com/", "Intel", "tech"),
    ("https://www.cisco.com/", "Cisco", "tech"),
    ("https://www.dell.com/", "Dell", "tech"),
    ("https://www.hp.com/", "HP", "tech"),
    
    # === E-COMMERCE (10) ===
    ("https://www.ebay.com/", "eBay", "ecommerce"),
    ("https://www.etsy.com/", "Etsy", "ecommerce"),
    ("https://www.target.com/", "Target", "ecommerce"),
    ("https://www.bestbuy.com/", "Best Buy", "ecommerce"),
    ("https://www.walmart.com/", "Walmart", "ecommerce"),
    ("https://www.shopify.com/", "Shopify", "ecommerce"),
    ("https://www.aliexpress.com/", "AliExpress", "ecommerce"),
    ("https://www.wayfair.com/", "Wayfair", "ecommerce"),
    ("https://www.overstock.com/", "Overstock", "ecommerce"),
    ("https://www.newegg.com/", "Newegg", "ecommerce"),
    
    # === SOCIAL MEDIA (10) ===
    ("https://twitter.com/", "Twitter/X", "social"),
    ("https://www.linkedin.com/", "LinkedIn", "social"),
    ("https://www.reddit.com/", "Reddit", "social"),
    ("https://www.pinterest.com/", "Pinterest", "social"),
    ("https://www.tumblr.com/", "Tumblr", "social"),
    ("https://www.instagram.com/", "Instagram", "social"),
    ("https://www.tiktok.com/", "TikTok", "social"),
    ("https://www.snapchat.com/", "Snapchat", "social"),
    ("https://www.youtube.com/", "YouTube", "social"),
    ("https://discord.com/", "Discord", "social"),
    
    # === NEWS & MEDIA (10) ===
    ("https://www.bbc.com/", "BBC", "news"),
    ("https://www.nytimes.com/", "NY Times", "news"),
    ("https://www.theguardian.com/", "The Guardian", "news"),
    ("https://www.washingtonpost.com/", "Washington Post", "news"),
    ("https://www.cnn.com/", "CNN", "news"),
    ("https://www.reuters.com/", "Reuters", "news"),
    ("https://www.bbc.co.uk/news", "BBC News", "news"),
    ("https://www.npr.org/", "NPR", "news"),
    ("https://www.aljazeera.com/", "Al Jazeera", "news"),
    ("https://www.foxnews.com/", "Fox News", "news"),
    
    # === EDUCATION (10) ===
    ("https://www.wikipedia.org/", "Wikipedia", "education"),
    ("https://www.khanacademy.org/", "Khan Academy", "education"),
    ("https://www.coursera.org/", "Coursera", "education"),
    ("https://developer.mozilla.org/", "MDN Web Docs", "education"),
    ("https://stackoverflow.com/", "Stack Overflow", "education"),
    ("https://www.edx.org/", "edX", "education"),
    ("https://www.udemy.com/", "Udemy", "education"),
    ("https://www.w3schools.com/", "W3Schools", "education"),
    ("https://www.codecademy.com/", "Codecademy", "education"),
    ("https://www.freecodecamp.org/", "freeCodeCamp", "education"),
    
    # === FINANCE (10) ===
    ("https://www.chase.com/", "Chase", "finance"),
    ("https://www.bankofamerica.com/", "Bank of America", "finance"),
    ("https://www.paypal.com/", "PayPal", "finance"),
    ("https://stripe.com/", "Stripe", "finance"),
    ("https://www.mint.com/", "Mint", "finance"),
    ("https://www.wellsfargo.com/", "Wells Fargo", "finance"),
    ("https://www.capitalone.com/", "Capital One", "finance"),
    ("https://www.discover.com/", "Discover", "finance"),
    ("https://www.fidelity.com/", "Fidelity", "finance"),
    ("https://www.vanguard.com/", "Vanguard", "finance"),
    
    # === HEALTHCARE (10) ===
    ("https://www.webmd.com/", "WebMD", "healthcare"),
    ("https://www.mayoclinic.org/", "Mayo Clinic", "healthcare"),
    ("https://www.healthline.com/", "Healthline", "healthcare"),
    ("https://www.cdc.gov/", "CDC", "healthcare"),
    ("https://www.who.int/", "WHO", "healthcare"),
    ("https://www.nih.gov/", "NIH", "healthcare"),
    ("https://www.medlineplus.gov/", "MedlinePlus", "healthcare"),
    ("https://www.clevelandclinic.org/", "Cleveland Clinic", "healthcare"),
    ("https://www.hopkinsmedicine.org/", "Johns Hopkins", "healthcare"),
    ("https://www.drugs.com/", "Drugs.com", "healthcare"),
    
    # === PRODUCTIVITY (5) ===
    ("https://www.notion.so/", "Notion", "productivity"),
    ("https://www.slack.com/", "Slack", "productivity"),
    ("https://www.trello.com/", "Trello", "productivity"),
    ("https://www.asana.com/", "Asana", "productivity"),
    ("https://www.monday.com/", "Monday", "productivity"),
    
    # === SIMPLE/BLOGS (10) ===
    ("https://news.ycombinator.com/", "Hacker News", "blog"),
    ("https://www.paulgraham.com/", "Paul Graham", "blog"),
    ("https://www.craigslist.org/", "Craigslist", "blog"),
    ("https://lite.cnn.com/", "CNN Lite", "blog"),
    ("https://text.npr.org/", "NPR Text", "blog"),
    ("https://www.drudgereport.com/", "Drudge Report", "blog"),
    ("https://slashdot.org/", "Slashdot", "blog"),
    ("https://www.metafilter.com/", "MetaFilter", "blog"),
    ("https://lobste.rs/", "Lobsters", "blog"),
    ("https://tildes.net/", "Tildes", "blog"),
]

@dataclass
class ComparisonResult:
    name: str
    url: str
    category: str
    
    # Baseline (No RAG)
    baseline_score: float = 0.0
    baseline_issues: int = 0
    baseline_time: float = 0.0
    baseline_enriched: int = 0
    
    # RAG-Enhanced
    rag_score: float = 0.0
    rag_issues: int = 0
    rag_time: float = 0.0
    rag_enriched: int = 0
    
    # Comparison metrics
    score_diff: float = 0.0
    issues_diff: int = 0
    enrichment_improvement: int = 0
    
    error: str = None

async def test_site_both_configs(url: str, name: str, category: str, semaphore) -> ComparisonResult:
    """Test one site with both RAG-disabled and RAG-enabled configurations."""
    async with semaphore:
        result = ComparisonResult(name=name, url=url, category=category)
        
        print(f"\n{'='*70}")
        print(f"  Testing: {name}")
        print(f"{'='*70}")
        
        # ========================================================================
        # CONFIGURATION 1: BASELINE (No RAG, No Cognitive)
        # ========================================================================
        print(f"  [1/2] Baseline (No RAG, No Cognitive)...", flush=True)
        baseline_start = time.time()
        try:
            baseline = await run_audit(
                url=url,
                scan_mode="deep",
                precision_profile="balanced",
                enable_enrichment=False,     # ❌ RAG disabled
                max_enrich_issues=0,         # ❌ RAG disabled
                enable_cognitive=False,      # ❌ Cognitive disabled
                await_enrichment=False,
            )
            result.baseline_time = time.time() - baseline_start
            result.baseline_score = baseline.get("score", 0)
            result.baseline_issues = baseline.get("total_issues", 0)
            result.baseline_enriched = sum(1 for iss in baseline.get("issues", []) if iss.get("rag_context"))
            
            print(f"    ✓ Score: {result.baseline_score:.1f}, Issues: {result.baseline_issues}, "
                  f"Time: {result.baseline_time:.1f}s, RAG: {result.baseline_enriched}")
        except Exception as e:
            result.error = f"Baseline failed: {str(e)[:100]}"
            print(f"    ✗ Error: {str(e)[:60]}")
            return result
        
        # ========================================================================
        # CONFIGURATION 2: RAG-ENHANCED (RAG enabled, No Cognitive)
        # ========================================================================
        print(f"  [2/2] RAG-Enhanced (RAG enabled, No Cognitive)...", flush=True)
        rag_start = time.time()
        try:
            rag_enhanced = await run_audit(
                url=url,
                scan_mode="deep",
                precision_profile="balanced",
                enable_enrichment=True,      # ✅ RAG enabled
                max_enrich_issues=20,        # ✅ RAG enabled (enrich up to 20 issues)
                enable_cognitive=False,      # ❌ Cognitive still disabled
                await_enrichment=True,
            )
            result.rag_time = time.time() - rag_start
            result.rag_score = rag_enhanced.get("score", 0)
            result.rag_issues = rag_enhanced.get("total_issues", 0)
            result.rag_enriched = sum(1 for iss in rag_enhanced.get("issues", []) if iss.get("rag_context"))
            
            print(f"    ✓ Score: {result.rag_score:.1f}, Issues: {result.rag_issues}, "
                  f"Time: {result.rag_time:.1f}s, RAG: {result.rag_enriched}")
        except Exception as e:
            result.error = f"RAG scan failed: {str(e)[:100]}"
            print(f"    ✗ Error: {str(e)[:60]}")
            return result
        
        # ========================================================================
        # CALCULATE IMPROVEMENTS
        # ========================================================================
        result.score_diff = result.rag_score - result.baseline_score
        result.issues_diff = result.rag_issues - result.baseline_issues
        result.enrichment_improvement = result.rag_enriched - result.baseline_enriched
        
        # Summary
        score_symbol = "📈" if result.score_diff > 0 else "📉" if result.score_diff < 0 else "➡️"
        issues_symbol = "🔍" if result.issues_diff > 0 else "✓" if result.issues_diff < 0 else "➡️"
        
        print(f"\n  📊 Impact Summary:")
        print(f"    {score_symbol} Score: {result.score_diff:+.1f} points")
        print(f"    {issues_symbol} Issues: {result.issues_diff:+d} ({'+' if result.issues_diff >= 0 else ''}{result.issues_diff})")
        print(f"    📚 Enrichment: +{result.enrichment_improvement} issues with knowledge")
        print(f"    ⏱️  Time overhead: {result.rag_time - result.baseline_time:+.1f}s")
        
        return result

async def main():
    print("\n" + "="*80)
    print("  🔬 RAG vs NO-RAG COMPARATIVE BENCHMARK - 100 SITES")
    print("  Comparing 100 sites with two configurations:")
    print("    1️⃣  Baseline: Pure engine accuracy (no RAG, no Cognitive)")
    print("    2️⃣  RAG-Enhanced: Knowledge-enriched results (RAG enabled)")
    print("  Running in PARALLEL with baseline benchmark test")
    print("="*80 + "\n")
    
    start_time = time.time()
    
    # Run tests with parallel execution (max 2 concurrent to keep it manageable)
    semaphore = asyncio.Semaphore(2)
    tasks = []
    
    for i, (url, name, category) in enumerate(TEST_SITES, 1):
        print(f"\n[{i}/{len(TEST_SITES)}] Queuing: {name}")
        task = test_site_both_configs(url, name, category, semaphore)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    # ============================================================================
    # COMPREHENSIVE ANALYSIS
    # ============================================================================
    
    print("\n\n" + "="*80)
    print("  📊 COMPREHENSIVE RAG IMPACT ANALYSIS")
    print("="*80)
    
    successful = [r for r in results if not r.error]
    errors = [r for r in results if r.error]
    
    print(f"\n📋 Execution Summary:")
    print(f"  Total sites tested: {len(TEST_SITES)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"  Avg time/site (both configs): {total_time/len(TEST_SITES):.1f}s")
    
    if successful:
        # ====================================================================
        # SCORE IMPACT
        # ====================================================================
        score_improvements = [r for r in successful if r.score_diff > 0]
        score_decreases = [r for r in successful if r.score_diff < 0]
        score_unchanged = [r for r in successful if r.score_diff == 0]
        avg_score_diff = sum(r.score_diff for r in successful) / len(successful)
        
        print(f"\n📈 Score Impact (RAG vs Baseline):")
        print(f"  Average change: {avg_score_diff:+.2f} points")
        print(f"  Improved: {len(score_improvements)} sites ({100*len(score_improvements)/len(successful):.1f}%)")
        print(f"  Decreased: {len(score_decreases)} sites ({100*len(score_decreases)/len(successful):.1f}%)")
        print(f"  Unchanged: {len(score_unchanged)} sites ({100*len(score_unchanged)/len(successful):.1f}%)")
        
        if score_improvements:
            best_improvement = max(score_improvements, key=lambda r: r.score_diff)
            print(f"  Best improvement: {best_improvement.name} ({best_improvement.score_diff:+.1f} points)")
        
        # ====================================================================
        # ISSUE DETECTION IMPACT
        # ====================================================================
        more_issues = [r for r in successful if r.issues_diff > 0]
        fewer_issues = [r for r in successful if r.issues_diff < 0]
        same_issues = [r for r in successful if r.issues_diff == 0]
        avg_issues_diff = sum(r.issues_diff for r in successful) / len(successful)
        
        print(f"\n🔍 Issue Detection Impact:")
        print(f"  Average change: {avg_issues_diff:+.1f} issues")
        print(f"  More issues found: {len(more_issues)} sites (more thorough)")
        print(f"  Fewer issues: {len(fewer_issues)} sites (better deduplication)")
        print(f"  Same issues: {len(same_issues)} sites")
        
        # ====================================================================
        # RAG ENRICHMENT SUCCESS RATE
        # ====================================================================
        enriched_sites = [r for r in successful if r.rag_enriched > 0]
        total_enriched = sum(r.rag_enriched for r in successful)
        total_baseline_issues = sum(r.baseline_issues for r in successful)
        enrichment_rate = (total_enriched / total_baseline_issues * 100) if total_baseline_issues > 0 else 0
        
        print(f"\n📚 RAG Knowledge Enrichment:")
        print(f"  Sites with RAG data: {len(enriched_sites)}/{len(successful)} ({100*len(enriched_sites)/len(successful):.1f}%)")
        print(f"  Total issues enriched: {total_enriched}")
        print(f"  Enrichment rate: {enrichment_rate:.1f}% of all issues")
        print(f"  Avg enriched/site: {total_enriched/len(successful):.1f}")
        
        if enriched_sites:
            best_enriched = max(enriched_sites, key=lambda r: r.rag_enriched)
            print(f"  Best enrichment: {best_enriched.name} ({best_enriched.rag_enriched} issues)")
        
        # ====================================================================
        # PERFORMANCE OVERHEAD
        # ====================================================================
        baseline_time_total = sum(r.baseline_time for r in successful)
        rag_time_total = sum(r.rag_time for r in successful)
        time_overhead = rag_time_total - baseline_time_total
        overhead_pct = (time_overhead / baseline_time_total * 100) if baseline_time_total > 0 else 0
        
        print(f"\n⏱️  Performance Impact:")
        print(f"  Baseline total time: {baseline_time_total:.1f}s")
        print(f"  RAG total time: {rag_time_total:.1f}s")
        print(f"  Overhead: +{time_overhead:.1f}s (+{overhead_pct:.1f}%)")
        print(f"  Avg overhead/site: {time_overhead/len(successful):.2f}s")
        
        # ====================================================================
        # CATEGORY BREAKDOWN
        # ====================================================================
        from collections import defaultdict
        by_category = defaultdict(lambda: {
            "count": 0,
            "baseline_score": 0,
            "rag_score": 0,
            "baseline_issues": 0,
            "rag_issues": 0,
            "rag_enriched": 0
        })
        
        for r in successful:
            by_category[r.category]["count"] += 1
            by_category[r.category]["baseline_score"] += r.baseline_score
            by_category[r.category]["rag_score"] += r.rag_score
            by_category[r.category]["baseline_issues"] += r.baseline_issues
            by_category[r.category]["rag_issues"] += r.rag_issues
            by_category[r.category]["rag_enriched"] += r.rag_enriched
        
        print(f"\n📂 Impact by Category:")
        print(f"  {'Category':<15} {'Sites':>5} {'Score Δ':>10} {'Issues Δ':>10} {'RAG %':>8}")
        print(f"  {'-'*60}")
        for cat in sorted(by_category.keys()):
            stats = by_category[cat]
            count = stats["count"]
            score_delta = (stats["rag_score"] - stats["baseline_score"]) / count
            issues_delta = (stats["rag_issues"] - stats["baseline_issues"]) / count
            rag_pct = (stats["rag_enriched"] / stats["rag_issues"] * 100) if stats["rag_issues"] > 0 else 0
            print(f"  {cat:<15} {count:>5} {score_delta:>+9.1f} {issues_delta:>+9.1f} {rag_pct:>7.1f}%")
        
        # ====================================================================
        # TOP PERFORMERS (RAG made biggest difference)
        # ====================================================================
        top_improvers = sorted([r for r in successful if r.enrichment_improvement > 0], 
                              key=lambda r: r.enrichment_improvement, reverse=True)[:5]
        
        if top_improvers:
            print(f"\n🏆 Top 5 Sites Where RAG Made Biggest Impact:")
            for i, r in enumerate(top_improvers, 1):
                print(f"  {i}. {r.name:<25} +{r.enrichment_improvement} enriched, "
                      f"Score: {r.score_diff:+.1f}, Issues: {r.issues_diff:+d}")
    
    # ============================================================================
    # SAVE RESULTS
    # ============================================================================
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_time": round(total_time, 2),
        "configuration_tested": {
            "baseline": "No RAG, No Cognitive (pure engine)",
            "rag_enhanced": "RAG enabled (max 20 issues), No Cognitive"
        },
        "summary": {
            "total_sites": len(TEST_SITES),
            "successful": len(successful),
            "errors": len(errors),
            "avg_score_improvement": round(avg_score_diff, 2) if successful else 0,
            "avg_issues_difference": round(avg_issues_diff, 1) if successful else 0,
            "enrichment_success_rate": round(100*len(enriched_sites)/len(successful), 1) if successful else 0,
            "performance_overhead_pct": round(overhead_pct, 1) if successful else 0
        },
        "results": [
            {
                "name": r.name,
                "url": r.url,
                "category": r.category,
                "baseline": {
                    "score": r.baseline_score,
                    "issues": r.baseline_issues,
                    "time": round(r.baseline_time, 2),
                    "enriched": r.baseline_enriched
                },
                "rag_enhanced": {
                    "score": r.rag_score,
                    "issues": r.rag_issues,
                    "time": round(r.rag_time, 2),
                    "enriched": r.rag_enriched
                },
                "impact": {
                    "score_diff": round(r.score_diff, 2),
                    "issues_diff": r.issues_diff,
                    "enrichment_gain": r.enrichment_improvement,
                    "time_overhead": round(r.rag_time - r.baseline_time, 2)
                },
                "error": r.error
            }
            for r in results
        ]
    }
    
    output_file = "tests/RAG_vs_BASELINE_comparison.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\n💾 Detailed results saved to: {output_file}")
    
    # ============================================================================
    # FINAL VERDICT
    # ============================================================================
    
    print("\n" + "="*80)
    print("  🎯 FINAL VERDICT: IS RAG WORTH IT?")
    print("="*80)
    
    if successful:
        if avg_score_diff > 0.5:
            print(f"  ✅ YES - RAG improves scores by avg {avg_score_diff:.1f} points")
        elif avg_score_diff < -0.5:
            print(f"  ⚠️  MIXED - RAG slightly decreases scores by {abs(avg_score_diff):.1f} points")
        else:
            print(f"  ➡️  NEUTRAL - RAG has minimal score impact ({avg_score_diff:.1f} points)")
        
        if len(enriched_sites) / len(successful) > 0.7:
            print(f"  ✅ YES - RAG successfully enriches {100*len(enriched_sites)/len(successful):.0f}% of sites")
        else:
            print(f"  ⚠️  LIMITED - RAG only enriches {100*len(enriched_sites)/len(successful):.0f}% of sites")
        
        if overhead_pct < 20:
            print(f"  ✅ YES - RAG overhead is acceptable ({overhead_pct:.1f}%)")
        else:
            print(f"  ⚠️  COSTLY - RAG adds significant overhead ({overhead_pct:.1f}%)")
        
        print(f"\n  💡 Recommendation:")
        if len(enriched_sites) / len(successful) > 0.5 and overhead_pct < 30:
            print(f"     RAG is VALUABLE - provides knowledge enrichment with minimal cost")
        elif len(enriched_sites) / len(successful) > 0.3:
            print(f"     RAG is USEFUL - moderate benefits, consider for production audits")
        else:
            print(f"     RAG needs IMPROVEMENT - low enrichment rate or high overhead")
    
    print("\n" + "="*80)
    print("  ✅ COMPARATIVE BENCHMARK COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
