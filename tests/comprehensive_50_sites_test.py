"""
BEACON Engine — World-Class 50-Site Comprehensive Test Suite
=============================================================

This test suite validates BEACON against 50 diverse real-world sites covering:
- Simple HTML sites
- Complex SPAs (React, Angular, Vue)
- Government & accessibility-focused sites  
- E-commerce platforms
- Social media
- News & media sites
- Educational platforms
- Financial services
- Healthcare
- Tech companies
- Internationalized sites

Goal: Achieve world-class accessibility auditing beyond YC-level quality.
"""
import asyncio
import json
import sys
import os
import time
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress verbose logs during bulk testing
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("playwright").setLevel(logging.WARNING)


@dataclass
class SiteTestCase:
    """Represents a site to test with expected characteristics."""
    url: str
    name: str
    category: str
    complexity: str  # simple, moderate, complex
    expected_score_range: tuple[int, int]  # (min, max) acceptable score
    notes: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# 50 DIVERSE TEST SITES - Carefully selected for comprehensive coverage
# ══════════════════════════════════════════════════════════════════════════════

TEST_SITES = [
    # ─── ACCESSIBILITY-FOCUSED SITES (should score well) ───────────────────────
    SiteTestCase("https://www.a11yproject.com/", "A11y Project", "accessibility", "simple", (70, 100)),
    SiteTestCase("https://webaim.org/", "WebAIM", "accessibility", "simple", (70, 100)),
    SiteTestCase("https://www.w3.org/WAI/", "W3C WAI", "accessibility", "moderate", (60, 100)),
    SiteTestCase("https://dequeuniversity.com/", "Deque University", "accessibility", "moderate", (65, 100)),
    SiteTestCase("https://inclusive-components.design/", "Inclusive Components", "accessibility", "simple", (70, 100)),
    
    # ─── GOVERNMENT SITES (legally required to be accessible) ──────────────────
    SiteTestCase("https://www.usa.gov/", "USA.gov", "government", "moderate", (50, 95)),
    SiteTestCase("https://www.gov.uk/", "GOV.UK", "government", "moderate", (60, 100)),
    SiteTestCase("https://www.canada.ca/en.html", "Canada.ca", "government", "moderate", (55, 95)),
    SiteTestCase("https://www.digital.gov/", "Digital.gov", "government", "simple", (60, 100)),
    SiteTestCase("https://www.section508.gov/", "Section508.gov", "government", "moderate", (65, 100)),
    
    # ─── TECH GIANTS (complex, should handle) ──────────────────────────────────
    SiteTestCase("https://www.microsoft.com/", "Microsoft", "tech", "complex", (10, 70)),
    SiteTestCase("https://www.apple.com/", "Apple", "tech", "complex", (5, 60)),
    SiteTestCase("https://www.google.com/", "Google", "tech", "moderate", (30, 80)),
    SiteTestCase("https://github.com/", "GitHub", "tech", "complex", (20, 70)),
    SiteTestCase("https://about.meta.com/", "Meta", "tech", "complex", (10, 60)),
    
    # ─── E-COMMERCE (complex with dynamic content) ─────────────────────────────
    SiteTestCase("https://www.amazon.com/", "Amazon", "ecommerce", "complex", (0, 50)),
    SiteTestCase("https://www.ebay.com/", "eBay", "ecommerce", "complex", (10, 60)),
    SiteTestCase("https://www.etsy.com/", "Etsy", "ecommerce", "complex", (15, 65)),
    SiteTestCase("https://www.target.com/", "Target", "ecommerce", "complex", (20, 70)),
    SiteTestCase("https://www.bestbuy.com/", "Best Buy", "ecommerce", "complex", (15, 65)),
    
    # ─── SOCIAL MEDIA (highly dynamic) ─────────────────────────────────────────
    SiteTestCase("https://twitter.com/", "Twitter/X", "social", "complex", (0, 50)),
    SiteTestCase("https://www.linkedin.com/", "LinkedIn", "social", "complex", (10, 60)),
    SiteTestCase("https://www.reddit.com/", "Reddit", "social", "complex", (0, 50)),
    SiteTestCase("https://www.pinterest.com/", "Pinterest", "social", "complex", (5, 55)),
    SiteTestCase("https://www.tumblr.com/", "Tumblr", "social", "complex", (10, 60)),
    
    # ─── NEWS & MEDIA ──────────────────────────────────────────────────────────
    SiteTestCase("https://www.bbc.com/", "BBC", "news", "complex", (30, 75)),
    SiteTestCase("https://www.nytimes.com/", "NY Times", "news", "complex", (20, 70)),
    SiteTestCase("https://www.theguardian.com/", "The Guardian", "news", "complex", (25, 70)),
    SiteTestCase("https://www.washingtonpost.com/", "Washington Post", "news", "complex", (15, 65)),
    SiteTestCase("https://news.ycombinator.com/", "Hacker News", "news", "simple", (0, 40), "Intentionally minimal HTML"),
    
    # ─── EDUCATIONAL ───────────────────────────────────────────────────────────
    SiteTestCase("https://www.wikipedia.org/", "Wikipedia", "education", "moderate", (40, 85)),
    SiteTestCase("https://www.khanacademy.org/", "Khan Academy", "education", "complex", (35, 80)),
    SiteTestCase("https://www.coursera.org/", "Coursera", "education", "complex", (30, 75)),
    SiteTestCase("https://developer.mozilla.org/en-US/", "MDN Web Docs", "education", "moderate", (50, 90)),
    SiteTestCase("https://stackoverflow.com/", "Stack Overflow", "education", "moderate", (25, 70)),
    
    # ─── FINANCIAL SERVICES ────────────────────────────────────────────────────
    SiteTestCase("https://www.chase.com/", "Chase", "finance", "complex", (20, 70)),
    SiteTestCase("https://www.bankofamerica.com/", "Bank of America", "finance", "complex", (25, 75)),
    SiteTestCase("https://www.paypal.com/", "PayPal", "finance", "complex", (30, 75)),
    SiteTestCase("https://stripe.com/", "Stripe", "finance", "moderate", (40, 85)),
    SiteTestCase("https://www.mint.com/", "Mint", "finance", "complex", (25, 70)),
    
    # ─── HEALTHCARE ────────────────────────────────────────────────────────────
    SiteTestCase("https://www.webmd.com/", "WebMD", "healthcare", "complex", (20, 65)),
    SiteTestCase("https://www.mayoclinic.org/", "Mayo Clinic", "healthcare", "moderate", (35, 80)),
    SiteTestCase("https://www.healthline.com/", "Healthline", "healthcare", "moderate", (30, 75)),
    SiteTestCase("https://www.cdc.gov/", "CDC", "healthcare", "moderate", (45, 90)),
    SiteTestCase("https://www.who.int/", "WHO", "healthcare", "moderate", (40, 85)),
    
    # ─── SIMPLE HTML / BLOGS ───────────────────────────────────────────────────
    SiteTestCase("https://www.paulgraham.com/", "Paul Graham Essays", "blog", "simple", (30, 80)),
    SiteTestCase("https://motherfuckingwebsite.com/", "MFWS", "blog", "simple", (40, 100), "Ultra-minimal HTML"),
    SiteTestCase("https://bettermotherfuckingwebsite.com/", "Better MFWS", "blog", "simple", (50, 100)),
    SiteTestCase("https://www.craigslist.org/", "Craigslist", "blog", "simple", (20, 70), "Intentionally basic"),
    SiteTestCase("https://lite.cnn.com/", "CNN Lite", "blog", "simple", (50, 95), "Accessibility-first design"),
]


@dataclass
class TestResult:
    """Result from testing a single site."""
    site: SiteTestCase
    fast_score: Optional[int] = None
    deep_score: Optional[int] = None
    fast_issues: int = 0
    deep_issues: int = 0
    fast_time: float = 0.0
    deep_time: float = 0.0
    fast_enrichment_status: str = "off"
    deep_enrichment_status: str = "off"
    fast_engines: list = None
    deep_engines: list = None
    wcag_scs: list = None
    severity_breakdown: dict = None
    error: Optional[str] = None
    passed: bool = False
    degraded: bool = False
    spa_framework: Optional[str] = None
    is_spa: bool = False
    browser_probe_metadata: dict = None
    
    def __post_init__(self):
        if self.fast_engines is None:
            self.fast_engines = []
        if self.deep_engines is None:
            self.deep_engines = []
        if self.wcag_scs is None:
            self.wcag_scs = []
        if self.severity_breakdown is None:
            self.severity_breakdown = {}
        if self.browser_probe_metadata is None:
            self.browser_probe_metadata = {}


async def run_single_site_test(
    site: SiteTestCase,
    timeout: int = 180,
    use_rag: bool = False,
    max_enrich_issues: int = 20,
    enable_cognitive: bool = True,
) -> TestResult:
    """Run fast + deep scan on a single site with timeout protection."""
    from app.services.audit_runner import run_audit
    
    result = TestResult(site=site)
    
    try:
        # ── FAST MODE ──────────────────────────────────────────────
        logger.info(f"[FAST] Testing {site.name}: {site.url}")
        fast_start = time.time()
        
        fast_result = await asyncio.wait_for(
            run_audit(
                site.url,
                scan_mode="fast",
                precision_profile="balanced",
                enable_enrichment=use_rag,
                max_enrich_issues=max_enrich_issues if use_rag else 0,
                enable_cognitive=False,
            ),
            timeout=60
        )
        
        result.fast_time = time.time() - fast_start
        result.fast_score = fast_result.get("score", 0)
        result.fast_issues = fast_result.get("total_issues", 0)
        result.fast_engines = fast_result.get("engines_used", [])
        result.fast_enrichment_status = fast_result.get("enrichment_status", "off")
        
        # Brief pause between scans
        await asyncio.sleep(1)
        
        # ── DEEP MODE ──────────────────────────────────────────────
        logger.info(f"[DEEP] Testing {site.name}: {site.url}")
        deep_start = time.time()
        
        deep_result = await asyncio.wait_for(
            run_audit(
                site.url,
                scan_mode="deep",
                precision_profile="balanced",
                enable_enrichment=use_rag,
                max_enrich_issues=max_enrich_issues if use_rag else 0,
                enable_cognitive=enable_cognitive,
            ),
            timeout=120
        )
        
        result.deep_time = time.time() - deep_start
        result.deep_score = deep_result.get("score", 0)
        result.deep_issues = deep_result.get("total_issues", 0)
        result.deep_engines = deep_result.get("engines_used", [])
        result.deep_enrichment_status = deep_result.get("enrichment_status", "off")
        result.wcag_scs = deep_result.get("wcag_scs_covered", [])
        result.degraded = deep_result.get("degraded_mode", False)
        
        # SPA detection info
        result.spa_framework = deep_result.get("spa_framework")
        result.is_spa = deep_result.get("is_spa", False)
        result.browser_probe_metadata = deep_result.get("browser_probe_metadata", {})
        
        # Severity breakdown
        issues = deep_result.get("issues", [])
        for issue in issues:
            sev = issue.get("severity", "unknown")
            result.severity_breakdown[sev] = result.severity_breakdown.get(sev, 0) + 1
        
        # Check if result is within expected range
        score = result.deep_score or result.fast_score or 0
        min_exp, max_exp = site.expected_score_range
        result.passed = min_exp <= score <= max_exp
        
    except asyncio.TimeoutError:
        result.error = "TIMEOUT"
        logger.warning(f"[TIMEOUT] {site.name} exceeded {timeout}s limit")
    except Exception as e:
        result.error = str(e)[:200]
        logger.error(f"[ERROR] {site.name}: {e}")
    
    return result


async def run_50_site_test(
    parallel_limit: int = 3,
    sites: list[SiteTestCase] = None,
    use_rag: bool = False,
    max_enrich_issues: int = 20,
    enable_cognitive: bool = True,
    output_path: Optional[str] = None,
) -> dict:
    """
    Run comprehensive 50-site test with parallel execution.
    
    Returns detailed report with:
    - Per-site results
    - Category summaries
    - Failure analysis
    - Performance metrics
    - Recommendations
    """
    if sites is None:
        sites = TEST_SITES
    
    print("\n" + "="*80)
    print("  [BEACON ENGINE] 50-SITE WORLD-CLASS AUDIT TEST")
    print("="*80)
    print(f"  Sites to test: {len(sites)}")
    print(f"  Parallel limit: {parallel_limit}")
    print(f"  RAG enrichment: {'ON' if use_rag else 'OFF'}")
    if use_rag:
        print(f"  Max enrich issues: {max_enrich_issues}")
    print(f"  Cognitive checks: {'ON' if enable_cognitive else 'OFF'}")
    print(f"  Started: {datetime.now().isoformat()}")
    print("="*80 + "\n")
    
    results: list[TestResult] = []
    semaphore = asyncio.Semaphore(parallel_limit)
    
    async def run_with_semaphore(site: SiteTestCase) -> TestResult:
        async with semaphore:
            return await run_single_site_test(
                site,
                use_rag=use_rag,
                max_enrich_issues=max_enrich_issues,
                enable_cognitive=enable_cognitive,
            )
    
    # Run all tests with controlled parallelism
    start_time = time.time()
    tasks = [run_with_semaphore(site) for site in sites]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = time.time() - start_time
    
    # Process results (handle any exceptions that slipped through)
    processed_results: list[TestResult] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            processed_results.append(TestResult(
                site=sites[i],
                error=str(r)[:200]
            ))
        else:
            processed_results.append(r)
    
    # ══════════════════════════════════════════════════════════════════════════
    # ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    # Category analysis
    category_stats = defaultdict(lambda: {
        "sites": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "avg_fast_score": 0,
        "avg_deep_score": 0,
        "avg_fast_time": 0,
        "avg_deep_time": 0,
        "total_issues": 0,
    })
    
    # Complexity analysis
    complexity_stats = defaultdict(lambda: {
        "sites": 0,
        "passed": 0,
        "errors": 0,
    })
    
    # Collect all failures for analysis
    failures = []
    successes = []
    errors = []
    degraded_sites = []
    
    for r in processed_results:
        cat = r.site.category
        comp = r.site.complexity
        
        category_stats[cat]["sites"] += 1
        complexity_stats[comp]["sites"] += 1
        
        if r.error:
            category_stats[cat]["errors"] += 1
            complexity_stats[comp]["errors"] += 1
            errors.append(r)
        elif r.passed:
            category_stats[cat]["passed"] += 1
            complexity_stats[comp]["passed"] += 1
            successes.append(r)
        else:
            category_stats[cat]["failed"] += 1
            failures.append(r)
        
        if r.degraded:
            degraded_sites.append(r)
        
        # Accumulate scores/times
        if r.fast_score is not None:
            category_stats[cat]["avg_fast_score"] += r.fast_score
        if r.deep_score is not None:
            category_stats[cat]["avg_deep_score"] += r.deep_score
        category_stats[cat]["avg_fast_time"] += r.fast_time
        category_stats[cat]["avg_deep_time"] += r.deep_time
        category_stats[cat]["total_issues"] += r.deep_issues
    
    # Calculate averages
    for cat, stats in category_stats.items():
        n = stats["sites"]
        if n > 0:
            stats["avg_fast_score"] = round(stats["avg_fast_score"] / n, 1)
            stats["avg_deep_score"] = round(stats["avg_deep_score"] / n, 1)
            stats["avg_fast_time"] = round(stats["avg_fast_time"] / n, 2)
            stats["avg_deep_time"] = round(stats["avg_deep_time"] / n, 2)
    
    # ══════════════════════════════════════════════════════════════════════════
    # REPORT
    # ══════════════════════════════════════════════════════════════════════════
    
    print("\n" + "="*80)
    print("  [SUMMARY] TEST RESULTS SUMMARY")
    print("="*80)
    
    total = len(processed_results)
    passed = len(successes)
    failed = len(failures)
    errored = len(errors)
    
    print(f"\n  Total Sites:     {total}")
    print(f"  [OK] Passed:       {passed} ({100*passed/total:.1f}%)")
    print(f"  [FAIL] Failed:       {failed} ({100*failed/total:.1f}%)")
    print(f"  [ERR] Errors:       {errored} ({100*errored/total:.1f}%)")
    print(f"  [DEG] Degraded:     {len(degraded_sites)} (browser fallback)")
    print(f"  [TIME] Total Time:   {total_time:.1f}s ({total_time/total:.1f}s avg)")
    
    # SPA detection stats
    spa_sites = [r for r in processed_results if r.is_spa]
    spa_frameworks = {}
    for r in spa_sites:
        fw = r.spa_framework or "generic"
        spa_frameworks[fw] = spa_frameworks.get(fw, 0) + 1
    
    if spa_sites:
        print(f"\n  [SPA] SPA Sites:     {len(spa_sites)} detected")
        for fw, count in sorted(spa_frameworks.items(), key=lambda x: -x[1]):
            print(f"      {fw}: {count}")
    
    # Category breakdown
    print("\n" + "-"*80)
    print("  BY CATEGORY")
    print("-"*80)
    print(f"  {'Category':<15} {'Sites':>6} {'Pass':>6} {'Fail':>6} {'Err':>5} {'AvgScore':>9} {'AvgTime':>8}")
    print("-"*80)
    for cat in sorted(category_stats.keys()):
        s = category_stats[cat]
        print(f"  {cat:<15} {s['sites']:>6} {s['passed']:>6} {s['failed']:>6} {s['errors']:>5} {s['avg_deep_score']:>8.1f} {s['avg_deep_time']:>7.1f}s")
    
    # Complexity breakdown
    print("\n" + "-"*80)
    print("  BY COMPLEXITY")
    print("-"*80)
    for comp in ["simple", "moderate", "complex"]:
        s = complexity_stats[comp]
        rate = 100 * s["passed"] / s["sites"] if s["sites"] > 0 else 0
        print(f"  {comp:<12}: {s['passed']}/{s['sites']} passed ({rate:.0f}%)")
    
    # SPA vs Non-SPA comparison
    spa_passed = sum(1 for r in spa_sites if r.passed)
    non_spa_sites = [r for r in processed_results if not r.is_spa and not r.error]
    non_spa_passed = sum(1 for r in non_spa_sites if r.passed)
    
    print("\n" + "-"*80)
    print("  SPA vs NON-SPA PERFORMANCE")
    print("-"*80)
    if spa_sites:
        spa_pass_rate = 100 * spa_passed / len(spa_sites)
        print(f"  SPA sites:     {spa_passed}/{len(spa_sites)} passed ({spa_pass_rate:.0f}%)")
    if non_spa_sites:
        non_spa_pass_rate = 100 * non_spa_passed / len(non_spa_sites)
        print(f"  Non-SPA sites: {non_spa_passed}/{len(non_spa_sites)} passed ({non_spa_pass_rate:.0f}%)")
    
    # Failed sites detail
    if failures:
        print("\n" + "-"*80)
        print("  [FAIL] FAILED SITES (score outside expected range)")
        print("-"*80)
        for r in failures:
            exp_min, exp_max = r.site.expected_score_range
            spa_tag = f" [SPA:{r.spa_framework}]" if r.is_spa else ""
            print(f"  • {r.site.name:<25} Score: {r.deep_score:>3}/100  Expected: {exp_min}-{exp_max}{spa_tag}")
            if r.severity_breakdown:
                print(f"    Severity: {r.severity_breakdown}")
    
    # Error sites detail
    if errors:
        print("\n" + "-"*80)
        print("  [ERR] ERROR SITES (could not complete scan)")
        print("-"*80)
        for r in errors:
            print(f"  • {r.site.name:<25} Error: {r.error[:50]}")
    
    # Degraded sites
    if degraded_sites:
        print("\n" + "-"*80)
        print("  [DEG] DEGRADED SCANS (browser engines failed, static-only results)")
        print("-"*80)
        for r in degraded_sites:
            print(f"  • {r.site.name:<25} Engines: {', '.join(r.deep_engines)}")
    
    # Top performing sites
    print("\n" + "-"*80)
    print("  [TOP10] TOP 10 PERFORMERS")
    print("-"*80)
    sorted_by_score = sorted(
        [r for r in processed_results if r.deep_score is not None],
        key=lambda x: x.deep_score,
        reverse=True
    )[:10]
    for i, r in enumerate(sorted_by_score, 1):
        spa_tag = f" [SPA]" if r.is_spa else ""
        print(f"  {i:2}. {r.site.name:<25} Score: {r.deep_score}/100 ({r.deep_time:.1f}s){spa_tag}")
    
    # Worst performing sites
    print("\n" + "-"*80)
    print("  [BOTTOM10] BOTTOM 10 PERFORMERS")
    print("-"*80)
    sorted_by_score_asc = sorted(
        [r for r in processed_results if r.deep_score is not None],
        key=lambda x: x.deep_score,
    )[:10]
    for i, r in enumerate(sorted_by_score_asc, 1):
        print(f"  {i:2}. {r.site.name:<25} Score: {r.deep_score}/100 Issues: {r.deep_issues}")
    
    # Performance outliers
    print("\n" + "-"*80)
    print("  [PERF] PERFORMANCE ANALYSIS")
    print("-"*80)
    fast_times = [r.fast_time for r in processed_results if r.fast_time > 0]
    deep_times = [r.deep_time for r in processed_results if r.deep_time > 0]
    
    if fast_times:
        print(f"  Fast mode:  avg={sum(fast_times)/len(fast_times):.1f}s  min={min(fast_times):.1f}s  max={max(fast_times):.1f}s")
    if deep_times:
        print(f"  Deep mode:  avg={sum(deep_times)/len(deep_times):.1f}s  min={min(deep_times):.1f}s  max={max(deep_times):.1f}s")
    
    slow_sites = [r for r in processed_results if r.deep_time > 60]
    if slow_sites:
        print(f"\n  Slow sites (>60s): {len(slow_sites)}")
        for r in slow_sites:
            print(f"    • {r.site.name}: {r.deep_time:.1f}s")
    
    # ══════════════════════════════════════════════════════════════════════════
    # IMPROVEMENT RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════════════════
    
    print("\n" + "="*80)
    print("  [REC] IMPROVEMENT RECOMMENDATIONS")
    print("="*80)
    
    recommendations = []
    
    # Analyze failure patterns
    if degraded_sites:
        recommendations.append({
            "priority": "HIGH",
            "area": "Browser Engine",
            "issue": f"{len(degraded_sites)} sites had degraded scans (browser failure)",
            "action": "Improve Playwright stability, add retry logic, handle CSP/Cloudflare better"
        })
    
    complex_failures = [r for r in failures if r.site.complexity == "complex"]
    if len(complex_failures) > len(failures) * 0.5:
        recommendations.append({
            "priority": "HIGH", 
            "area": "Complex Site Support",
            "issue": f"{len(complex_failures)} complex sites failed",
            "action": "Improve SPA detection, handle React/Angular hydration, wait for dynamic content"
        })
    
    if errors:
        timeout_errors = [r for r in errors if r.error == "TIMEOUT"]
        if timeout_errors:
            recommendations.append({
                "priority": "MEDIUM",
                "area": "Performance",
                "issue": f"{len(timeout_errors)} sites timed out",
                "action": "Optimize slow checks, add early-exit for problematic sites"
            })
    
    ecommerce_failures = [r for r in failures if r.site.category == "ecommerce"]
    if ecommerce_failures:
        recommendations.append({
            "priority": "MEDIUM",
            "area": "E-commerce Support",
            "issue": f"{len(ecommerce_failures)} e-commerce sites failed",
            "action": "Improve handling of lazy-loaded products, modal dialogs, cart systems"
        })
    
    social_failures = [r for r in failures if r.site.category == "social"]
    if social_failures:
        recommendations.append({
            "priority": "MEDIUM",
            "area": "Social Media Support",  
            "issue": f"{len(social_failures)} social media sites failed",
            "action": "Handle infinite scroll, embedded media, dynamic feeds"
        })
    
    # SPA-specific recommendations
    spa_failures = [r for r in failures if r.is_spa]
    if spa_failures:
        frameworks_failed = set(r.spa_framework or "generic" for r in spa_failures)
        recommendations.append({
            "priority": "MEDIUM",
            "area": "SPA Framework Support",
            "issue": f"{len(spa_failures)} SPA sites failed ({', '.join(frameworks_failed)})",
            "action": "Improve hydration detection and waiting logic for these frameworks"
        })
    
    for rec in recommendations:
        print(f"\n  [{rec['priority']}] {rec['area']}")
        print(f"    Issue:  {rec['issue']}")
        print(f"    Action: {rec['action']}")
    
    if not recommendations:
        print("\n  [OK] No critical issues found! Engine performing well.")
    
    # ══════════════════════════════════════════════════════════════════════════
    # SAVE REPORT
    # ══════════════════════════════════════════════════════════════════════════
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_time_seconds": round(total_time, 2),
        "configuration": {
            "rag_enabled": use_rag,
            "max_enrich_issues": max_enrich_issues if use_rag else 0,
            "cognitive_enabled": enable_cognitive,
        },
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errored,
            "degraded": len(degraded_sites),
            "spa_detected": len(spa_sites),
            "pass_rate": round(100 * passed / total, 1),
        },
        "spa_detection": {
            "total_spa_sites": len(spa_sites),
            "frameworks": spa_frameworks,
            "spa_pass_rate": round(100 * spa_passed / len(spa_sites), 1) if spa_sites else 0,
        },
        "category_stats": dict(category_stats),
        "complexity_stats": dict(complexity_stats),
        "results": [
            {
                "name": r.site.name,
                "url": r.site.url,
                "category": r.site.category,
                "complexity": r.site.complexity,
                "fast_score": r.fast_score,
                "deep_score": r.deep_score,
                "fast_issues": r.fast_issues,
                "deep_issues": r.deep_issues,
                "fast_time": round(r.fast_time, 2),
                "deep_time": round(r.deep_time, 2),
                "fast_enrichment_status": r.fast_enrichment_status,
                "deep_enrichment_status": r.deep_enrichment_status,
                "engines": r.deep_engines,
                "wcag_scs": r.wcag_scs,
                "severity": r.severity_breakdown,
                "passed": r.passed,
                "degraded": r.degraded,
                "error": r.error,
                "is_spa": r.is_spa,
                "spa_framework": r.spa_framework,
            }
            for r in processed_results
        ],
        "failures": [
            {"name": r.site.name, "score": r.deep_score, "expected": r.site.expected_score_range}
            for r in failures
        ],
        "errors": [
            {"name": r.site.name, "error": r.error}
            for r in errors
        ],
        "recommendations": recommendations,
    }
    
    # Save to file
    if output_path:
        out_path = output_path
    else:
        filename = "50_sites_test_results_rag.json" if use_rag else "50_sites_test_results.json"
        out_path = os.path.join(os.path.dirname(__file__), filename)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n  [REPORT] Full report saved to: {out_path}")
    print("="*80 + "\n")
    
    return report


async def run_quick_test(n_sites: int = 10):
    """Run a quick test with first N sites for rapid iteration."""
    return await run_50_site_test(parallel_limit=2, sites=TEST_SITES[:n_sites])


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="BEACON 50-Site Test Suite")
    parser.add_argument("--quick", type=int, default=0, help="Quick test with N sites")
    parser.add_argument("--parallel", type=int, default=3, help="Parallel site limit")
    parser.add_argument("--category", type=str, default=None, help="Test specific category only")
    parser.add_argument("--rag", action="store_true", help="Enable RAG enrichment during fast and deep scans")
    parser.add_argument("--max-enrich-issues", type=int, default=20, help="Max issues to enrich with RAG context")
    parser.add_argument("--no-cognitive", action="store_true", help="Disable cognitive checks for deep scan")
    parser.add_argument("--output", type=str, default=None, help="Custom output JSON path")
    args = parser.parse_args()
    
    if args.category:
        sites = [s for s in TEST_SITES if s.category == args.category]
        print(f"Testing {len(sites)} sites in category: {args.category}")
    elif args.quick > 0:
        sites = TEST_SITES[:args.quick]
        print(f"Quick test with {args.quick} sites")
    else:
        sites = TEST_SITES
    
    asyncio.run(
        run_50_site_test(
            parallel_limit=args.parallel,
            sites=sites,
            use_rag=args.rag,
            max_enrich_issues=args.max_enrich_issues,
            enable_cognitive=not args.no_cognitive,
            output_path=args.output,
        )
    )
