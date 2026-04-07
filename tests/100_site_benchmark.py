#!/usr/bin/env python3
"""
Large-Site Accessibility Audit Benchmark
========================================
Tests BEACON engine with both FAST and DEEP scans on a diverse real-world site set.

Usage:
    python tests/100_site_benchmark.py
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.audit_runner import run_audit

# =============================================================================
# DIVERSE TEST SITES
# =============================================================================

SITES_100 = [
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
class BenchmarkResult:
    name: str
    url: str
    category: str
    fast_score: float = 0.0
    deep_score: float = 0.0
    fast_issues: int = 0
    deep_issues: int = 0
    fast_time: float = 0.0
    deep_time: float = 0.0
    fast_engines: list = None
    deep_engines: list = None
    fast_degraded: bool = False
    deep_degraded: bool = False
    spa_framework: str = None
    is_spa: bool = False
    error: str = None

async def test_site(url: str, name: str, category: str, semaphore) -> BenchmarkResult:
    """Test a single site with both fast and deep scans."""
    async with semaphore:
        result = BenchmarkResult(name=name, url=url, category=category, fast_engines=[], deep_engines=[])
        
        # FAST SCAN
        print(f"  [{name}] Running FAST scan...", flush=True)
        fast_start = time.time()
        try:
            fast_result = await run_audit(
                url=url,
                scan_mode="fast",
                precision_profile="balanced",
                enable_enrichment=False,
                enable_cognitive=False,
            )
            result.fast_time = time.time() - fast_start
            result.fast_score = fast_result.get("score", 0)
            result.fast_issues = fast_result.get("total_issues", 0)
            result.fast_engines = fast_result.get("engines_used", [])
            result.fast_degraded = fast_result.get("degraded_mode", False)
        except Exception as e:
            result.error = f"Fast scan failed: {str(e)[:100]}"
            print(f"    ✗ Fast scan error: {str(e)[:60]}")
            return result
        
        # DEEP SCAN
        print(f"  [{name}] Running DEEP scan...", flush=True)
        deep_start = time.time()
        try:
            deep_result = await run_audit(
                url=url,
                scan_mode="deep",
                precision_profile="balanced",
                enable_enrichment=False,
            )
            result.deep_time = time.time() - deep_start
            result.deep_score = deep_result.get("score", 0)
            result.deep_issues = deep_result.get("total_issues", 0)
            result.deep_engines = deep_result.get("engines_used", [])
            result.deep_degraded = deep_result.get("degraded_mode", False)
            result.spa_framework = deep_result.get("spa_framework")
            result.is_spa = deep_result.get("is_spa", False)
        except Exception as e:
            result.error = f"Deep scan failed: {str(e)[:100]}"
            print(f"    ✗ Deep scan error: {str(e)[:60]}")
        
        # Report
        improvement = ((result.deep_issues - result.fast_issues) / result.fast_issues * 100) if result.fast_issues > 0 else 0
        spa_badge = f" [{result.spa_framework}]" if result.spa_framework else ""
        print(f"    ✓ Fast: {result.fast_score:.1f} ({result.fast_issues} issues, {result.fast_time:.1f}s)")
        print(f"    ✓ Deep: {result.deep_score:.1f} ({result.deep_issues} issues, {result.deep_time:.1f}s) +{improvement:.0f}%{spa_badge}")
        
        return result

async def main():
    total_sites = len(SITES_100)
    print("\n" + "="*80)
    print(f"  🌐 BEACON {total_sites}-SITE ACCESSIBILITY BENCHMARK")
    print("  Testing with FAST + DEEP scans (no RAG enrichment)")
    print("="*80 + "\n")
    
    start_time = time.time()
    
    # Run tests with parallel execution (max 3 concurrent)
    semaphore = asyncio.Semaphore(3)
    tasks = []
    
    for i, (url, name, category) in enumerate(SITES_100, 1):
        print(f"[{i}/{total_sites}] Queuing {name}...")
        task = test_site(url, name, category, semaphore)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    # =============================================================================
    # ANALYSIS
    # =============================================================================
    
    print("\n" + "="*80)
    print("  📊 BENCHMARK RESULTS")
    print("="*80)
    
    successful = [r for r in results if not r.error]
    errors = [r for r in results if r.error]
    spas = [r for r in successful if r.is_spa]
    
    print(f"\nExecution Summary:")
    print(f"  Total sites: {total_sites}")
    print(f"  Successful: {len(successful)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"  Avg time/site: {total_time/total_sites:.1f}s")
    
    if successful:
        # Score statistics
        fast_scores = [r.fast_score for r in successful]
        deep_scores = [r.deep_score for r in successful]
        
        print(f"\n📈 Score Statistics:")
        print(f"  Fast Scan - Avg: {sum(fast_scores)/len(fast_scores):.1f}, Min: {min(fast_scores):.1f}, Max: {max(fast_scores):.1f}")
        print(f"  Deep Scan - Avg: {sum(deep_scores)/len(deep_scores):.1f}, Min: {min(deep_scores):.1f}, Max: {max(deep_scores):.1f}")
        
        # Issue statistics
        fast_issues_total = sum(r.fast_issues for r in successful)
        deep_issues_total = sum(r.deep_issues for r in successful)
        improvement = ((deep_issues_total - fast_issues_total) / fast_issues_total * 100) if fast_issues_total > 0 else 0
        
        print(f"\n🔍 Issue Detection:")
        print(f"  Fast Scan - Total: {fast_issues_total}, Avg: {fast_issues_total/len(successful):.1f}/site")
        print(f"  Deep Scan - Total: {deep_issues_total}, Avg: {deep_issues_total/len(successful):.1f}/site")
        print(f"  Improvement: +{improvement:.1f}% more issues with Deep scan")
        
        # Performance
        fast_times = [r.fast_time for r in successful]
        deep_times = [r.deep_time for r in successful]
        
        print(f"\n⚡ Performance:")
        print(f"  Fast Scan - Avg: {sum(fast_times)/len(fast_times):.1f}s, Max: {max(fast_times):.1f}s")
        print(f"  Deep Scan - Avg: {sum(deep_times)/len(deep_times):.1f}s, Max: {max(deep_times):.1f}s")
        print(f"  Slowdown: {sum(deep_times)/sum(fast_times):.1f}x")
        
        # SPA detection
        if spas:
            frameworks = defaultdict(int)
            for r in spas:
                frameworks[r.spa_framework or "unknown"] += 1
            
            print(f"\n🔧 SPA Detection:")
            print(f"  Total SPAs: {len(spas)} ({100*len(spas)/len(successful):.1f}%)")
            for fw, count in sorted(frameworks.items(), key=lambda x: -x[1]):
                print(f"    {fw}: {count} sites")
        
        # Category breakdown
        by_category = defaultdict(lambda: {"count": 0, "fast_score": 0, "deep_score": 0, "fast_issues": 0, "deep_issues": 0})
        for r in successful:
            by_category[r.category]["count"] += 1
            by_category[r.category]["fast_score"] += r.fast_score
            by_category[r.category]["deep_score"] += r.deep_score
            by_category[r.category]["fast_issues"] += r.fast_issues
            by_category[r.category]["deep_issues"] += r.deep_issues
        
        print(f"\n📂 By Category:")
        for cat in sorted(by_category.keys()):
            stats = by_category[cat]
            count = stats["count"]
            print(f"  {cat:15} {count:2} sites | "
                  f"Fast: {stats['fast_score']/count:5.1f} ({stats['fast_issues']/count:4.1f} issues) | "
                  f"Deep: {stats['deep_score']/count:5.1f} ({stats['deep_issues']/count:4.1f} issues)")
    
    # Save results
    timeout_count = sum(1 for r in errors if "timeout" in str(r.error).lower())
    degraded_count = sum(1 for r in successful if r.fast_degraded or r.deep_degraded)
    fast_mode_count = sum(1 for r in results if r.fast_time > 0)

    def _p95(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = max(0, min(len(ordered) - 1, int(0.95 * (len(ordered) - 1))))
        return round(float(ordered[idx]), 2)

    fast_times_all = [r.fast_time for r in results if r.fast_time > 0]
    avg_runtime = round(total_time / total_sites, 2) if total_sites else 0.0

    output = {
        "timestamp": datetime.now().isoformat(),
        "total_time": round(total_time, 2),
        "summary": {
            "total": total_sites,
            "successful": len(successful),
            "errors": len(errors),
            "spas_detected": len(spas),
        },
        "kpi": {
            "success_rate": round((len(successful) / total_sites) * 100, 1) if total_sites else 0.0,
            "degraded_rate": round((degraded_count / total_sites) * 100, 1) if total_sites else 0.0,
            "precision": None,
            "recall": None,
            "f1": None,
            "spa_precision": None,
            "spa_recall": None,
            "rag_completion": None,
            "timeout_rate": round((timeout_count / total_sites) * 100, 1) if total_sites else 0.0,
            "avg_runtime": avg_runtime,
            "fast_mode_p95_time": _p95(fast_times_all),
            "fast_mode_usage": round((fast_mode_count / total_sites) * 100, 1) if total_sites else 0.0,
        },
        "results": [
            {
                "name": r.name,
                "url": r.url,
                "category": r.category,
                "fast_score": r.fast_score,
                "deep_score": r.deep_score,
                "fast_issues": r.fast_issues,
                "deep_issues": r.deep_issues,
                "fast_time": round(r.fast_time, 2),
                "deep_time": round(r.deep_time, 2),
                "fast_engines": r.fast_engines,
                "deep_engines": r.deep_engines,
                "fast_degraded": r.fast_degraded,
                "deep_degraded": r.deep_degraded,
                "spa_framework": r.spa_framework,
                "is_spa": r.is_spa,
                "error": r.error,
            }
            for r in results
        ]
    }
    
    output_file = "tests/100_site_benchmark_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    print("\n" + "="*80)
    print("  ✅ BENCHMARK COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
