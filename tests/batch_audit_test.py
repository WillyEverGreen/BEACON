#!/usr/bin/env python3
"""
World-Class Batch Audit Test Suite
===================================
Tests BEACON accessibility engine against diverse real-world websites.

This script can be run standalone to validate the engine's performance
across different categories and complexity levels.

Usage:
    python tests/batch_audit_test.py                    # Full 50 sites
    python tests/batch_audit_test.py --quick 10         # Quick 10 sites
    python tests/batch_audit_test.py --category tech    # Only tech sites
    python tests/batch_audit_test.py --parallel 3       # 3 concurrent
"""

import asyncio
import sys
import os
import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict
from typing import Optional, Dict, List, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.audit_runner import run_audit


# =============================================================================
# TEST SITE DEFINITIONS
# =============================================================================

@dataclass
class TestSite:
    name: str
    url: str
    category: str
    complexity: str  # simple, moderate, complex
    expected_score_min: int = 40  # Minimum expected score
    expected_score_max: int = 100  # Maximum expected score


WORLD_CLASS_TEST_SITES = [
    # ============== CATEGORY 1: Accessibility-Focused Sites ==============
    # These should score VERY high (90+)
    TestSite("A11y Project", "https://www.a11yproject.com/", "accessibility", "moderate", 85, 100),
    TestSite("WebAIM", "https://webaim.org/", "accessibility", "simple", 85, 100),
    TestSite("W3C WAI", "https://www.w3.org/WAI/", "accessibility", "moderate", 80, 100),
    TestSite("Deque", "https://www.deque.com/", "accessibility", "complex", 75, 100),
    TestSite("Inclusive Design", "https://inclusivedesignprinciples.org/", "accessibility", "simple", 85, 100),
    
    # ============== CATEGORY 2: Government Sites ==============
    # Usually well-tested for WCAG compliance
    TestSite("USA.gov", "https://www.usa.gov/", "government", "complex", 70, 100),
    TestSite("GOV.UK", "https://www.gov.uk/", "government", "complex", 80, 100),
    TestSite("Canada.ca", "https://www.canada.ca/en.html", "government", "complex", 70, 100),
    TestSite("NHS UK", "https://www.nhs.uk/", "government", "complex", 80, 100),
    TestSite("Australia.gov", "https://www.australia.gov.au/", "government", "complex", 65, 100),
    
    # ============== CATEGORY 3: Tech Giants ==============
    # Complex SPAs, but usually good accessibility
    TestSite("Microsoft", "https://www.microsoft.com/", "tech", "complex", 60, 95),
    TestSite("Apple", "https://www.apple.com/", "tech", "complex", 60, 95),
    TestSite("Google Search", "https://www.google.com/", "tech", "complex", 65, 100),
    TestSite("GitHub", "https://github.com/", "tech", "complex", 55, 90),
    TestSite("MDN Web Docs", "https://developer.mozilla.org/", "tech", "complex", 70, 100),
    
    # ============== CATEGORY 4: E-commerce ==============
    # Complex interactions, cart systems, modals
    TestSite("Amazon", "https://www.amazon.com/", "ecommerce", "complex", 40, 80),
    TestSite("Target", "https://www.target.com/", "ecommerce", "complex", 50, 85),
    TestSite("Best Buy", "https://www.bestbuy.com/", "ecommerce", "complex", 45, 80),
    TestSite("Etsy", "https://www.etsy.com/", "ecommerce", "complex", 45, 80),
    TestSite("eBay", "https://www.ebay.com/", "ecommerce", "complex", 40, 75),
    
    # ============== CATEGORY 5: Social Media ==============
    # Highly dynamic, infinite scroll, complex
    TestSite("LinkedIn", "https://www.linkedin.com/", "social", "complex", 40, 80),
    TestSite("Pinterest", "https://www.pinterest.com/", "social", "complex", 30, 70),
    TestSite("Reddit", "https://www.reddit.com/", "social", "complex", 35, 75),
    TestSite("Medium", "https://medium.com/", "social", "complex", 50, 85),
    TestSite("Dribbble", "https://dribbble.com/", "social", "complex", 45, 80),
    
    # ============== CATEGORY 6: News & Media ==============
    # Lots of images, videos, complex layouts
    TestSite("BBC", "https://www.bbc.com/", "news", "complex", 50, 85),
    TestSite("NY Times", "https://www.nytimes.com/", "news", "complex", 45, 80),
    TestSite("The Guardian", "https://www.theguardian.com/", "news", "complex", 50, 85),
    TestSite("NPR", "https://www.npr.org/", "news", "complex", 55, 90),
    TestSite("Al Jazeera", "https://www.aljazeera.com/", "news", "complex", 45, 80),
    
    # ============== CATEGORY 7: Educational ==============
    # Complex content, usually good accessibility
    TestSite("Wikipedia", "https://www.wikipedia.org/", "education", "simple", 70, 100),
    TestSite("Khan Academy", "https://www.khanacademy.org/", "education", "complex", 60, 90),
    TestSite("Coursera", "https://www.coursera.org/", "education", "complex", 55, 85),
    TestSite("W3Schools", "https://www.w3schools.com/", "education", "moderate", 50, 80),
    TestSite("edX", "https://www.edx.org/", "education", "complex", 55, 85),
    
    # ============== CATEGORY 8: Financial ==============
    # Security-focused, often complex
    TestSite("Chase", "https://www.chase.com/", "financial", "complex", 55, 85),
    TestSite("PayPal", "https://www.paypal.com/", "financial", "complex", 50, 80),
    TestSite("Stripe", "https://stripe.com/", "financial", "complex", 60, 90),
    TestSite("Fidelity", "https://www.fidelity.com/", "financial", "complex", 50, 85),
    TestSite("Intuit", "https://www.intuit.com/", "financial", "complex", 55, 85),
    
    # ============== CATEGORY 9: Healthcare ==============
    # Critical accessibility needs
    TestSite("WebMD", "https://www.webmd.com/", "healthcare", "complex", 45, 80),
    TestSite("CDC", "https://www.cdc.gov/", "healthcare", "moderate", 65, 95),
    TestSite("WHO", "https://www.who.int/", "healthcare", "complex", 55, 85),
    TestSite("Mayo Clinic", "https://www.mayoclinic.org/", "healthcare", "complex", 50, 80),
    TestSite("Healthline", "https://www.healthline.com/", "healthcare", "complex", 45, 80),
    
    # ============== CATEGORY 10: Simple/Blog Sites ==============
    # Test detection on simpler HTML
    TestSite("Hacker News", "https://news.ycombinator.com/", "blog", "simple", 20, 60),
    TestSite("Paul Graham", "https://paulgraham.com/", "blog", "simple", 40, 75),
    TestSite("Craigslist", "https://www.craigslist.org/", "blog", "simple", 30, 65),
    TestSite("CNN Lite", "https://lite.cnn.com/", "blog", "simple", 50, 80),
    TestSite("Lobste.rs", "https://lobste.rs/", "blog", "simple", 40, 75),
]


# =============================================================================
# TEST RESULT STRUCTURE
# =============================================================================

@dataclass
class AuditResult:
    site: TestSite
    fast_score: Optional[float] = None
    deep_score: Optional[float] = None
    fast_issues: int = 0
    deep_issues: int = 0
    fast_time: float = 0.0
    deep_time: float = 0.0
    passed: bool = False
    degraded: bool = False
    error: Optional[str] = None
    engines_used: List[str] = field(default_factory=list)
    wcag_criteria: List[str] = field(default_factory=list)
    severity_breakdown: Dict[str, int] = field(default_factory=dict)
    is_spa: bool = False
    spa_framework: Optional[str] = None


# =============================================================================
# AUDIT EXECUTION
# =============================================================================

async def audit_single_site(site: TestSite, run_deep: bool = True) -> AuditResult:
    """Run audit on a single site and return results."""
    result = AuditResult(site=site)
    
    # Fast audit
    fast_start = time.time()
    try:
        fast_result = await run_audit(url=site.url, scan_mode="fast", precision_profile="balanced")
        result.fast_time = time.time() - fast_start
        result.fast_score = fast_result.get("score", 0)
        result.fast_issues = fast_result.get("total_issues", 0)
        result.degraded = fast_result.get("degraded_mode", False)
    except Exception as e:
        result.error = f"Fast audit failed: {str(e)[:100]}"
        return result
    
    # Deep audit (if enabled)
    if run_deep and not result.degraded:
        deep_start = time.time()
        try:
            deep_result = await run_audit(url=site.url, scan_mode="deep", precision_profile="balanced")
            result.deep_time = time.time() - deep_start
            result.deep_score = deep_result.get("score", 0)
            result.deep_issues = deep_result.get("total_issues", 0)
            result.engines_used = deep_result.get("engines_used", [])
            result.is_spa = deep_result.get("is_spa", False)
            result.spa_framework = deep_result.get("spa_framework")
            
            # Extract WCAG criteria and severity
            issues = deep_result.get("issues", [])
            result.wcag_criteria = list(set(i.get("wcag_criterion", "N/A") for i in issues))
            
            severity_counts = defaultdict(int)
            for issue in issues:
                sev = issue.get("severity", "unknown")
                severity_counts[sev] += 1
            result.severity_breakdown = dict(severity_counts)
            
        except Exception as e:
            result.error = f"Deep audit failed: {str(e)[:100]}"
    
    # Determine pass/fail
    score_to_check = result.deep_score if result.deep_score is not None else result.fast_score
    if score_to_check is not None:
        result.passed = site.expected_score_min <= score_to_check <= site.expected_score_max
    
    return result


async def run_batch_audit(
    sites: List[TestSite],
    parallel: int = 2,
    run_deep: bool = True,
    progress_callback=None
) -> List[AuditResult]:
    """Run batch audit on multiple sites with parallel execution."""
    results = []
    semaphore = asyncio.Semaphore(parallel)
    
    async def audit_with_semaphore(site: TestSite, index: int) -> AuditResult:
        async with semaphore:
            if progress_callback:
                progress_callback(f"[{index}/{len(sites)}] Testing {site.name}...")
            result = await audit_single_site(site, run_deep=run_deep)
            return result
    
    tasks = [audit_with_semaphore(site, i+1) for i, site in enumerate(sites)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions
    final_results = []
    for site, result in zip(sites, results):
        if isinstance(result, Exception):
            final_results.append(AuditResult(
                site=site,
                error=f"Exception: {str(result)[:100]}"
            ))
        else:
            final_results.append(result)
    
    return final_results


# =============================================================================
# ANALYSIS & REPORTING
# =============================================================================

def analyze_results(results: List[AuditResult]) -> Dict[str, Any]:
    """Analyze batch audit results and generate insights."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    errored = sum(1 for r in results if r.error)
    degraded = sum(1 for r in results if r.degraded)
    
    # Category analysis
    by_category = defaultdict(lambda: {"total": 0, "passed": 0, "errors": 0})
    for r in results:
        by_category[r.site.category]["total"] += 1
        if r.passed:
            by_category[r.site.category]["passed"] += 1
        if r.error:
            by_category[r.site.category]["errors"] += 1
    
    # Complexity analysis
    by_complexity = defaultdict(lambda: {"total": 0, "passed": 0, "errors": 0})
    for r in results:
        by_complexity[r.site.complexity]["total"] += 1
        if r.passed:
            by_complexity[r.site.complexity]["passed"] += 1
        if r.error:
            by_complexity[r.site.complexity]["errors"] += 1
    
    # SPA analysis
    spa_results = [r for r in results if r.is_spa]
    spa_frameworks = defaultdict(int)
    for r in spa_results:
        spa_frameworks[r.spa_framework or "Unknown"] += 1
    
    # Score statistics
    valid_scores = [r.deep_score for r in results if r.deep_score is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
    
    # Performance stats
    fast_times = [r.fast_time for r in results if r.fast_time > 0]
    deep_times = [r.deep_time for r in results if r.deep_time > 0]
    
    # Common issues
    all_severities = defaultdict(int)
    for r in results:
        for sev, count in r.severity_breakdown.items():
            all_severities[sev] += count
    
    return {
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed - errored,
            "errors": errored,
            "degraded": degraded,
            "pass_rate": round(100 * passed / total, 1) if total > 0 else 0,
        },
        "scores": {
            "average": round(avg_score, 1),
            "min": min(valid_scores) if valid_scores else 0,
            "max": max(valid_scores) if valid_scores else 0,
        },
        "performance": {
            "avg_fast_time": round(sum(fast_times) / len(fast_times), 2) if fast_times else 0,
            "avg_deep_time": round(sum(deep_times) / len(deep_times), 2) if deep_times else 0,
            "max_deep_time": round(max(deep_times), 2) if deep_times else 0,
        },
        "by_category": dict(by_category),
        "by_complexity": dict(by_complexity),
        "spa": {
            "total": len(spa_results),
            "frameworks": dict(spa_frameworks),
        },
        "severity_breakdown": dict(all_severities),
    }


def print_report(results: List[AuditResult], analysis: Dict[str, Any], total_time: float):
    """Print a comprehensive test report."""
    summary = analysis["summary"]
    
    print("\n" + "═" * 70)
    print("  🌐 BEACON WORLD-CLASS ACCESSIBILITY AUDIT - TEST REPORT")
    print("═" * 70)
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print(f"  Total Time: {total_time:.1f}s")
    
    # Summary
    print("\n┌" + "─" * 68 + "┐")
    print(f"│ {'SUMMARY':^66} │")
    print("├" + "─" * 68 + "┤")
    print(f"│ Total Sites:  {summary['total']:>3}  │  Passed:    {summary['passed']:>3}  │  Failed:   {summary['failed']:>3}  │  Errors:  {summary['errors']:>3}  │")
    print(f"│ Pass Rate:    {summary['pass_rate']:>5.1f}%  │  Degraded:  {summary['degraded']:>3}  │  SPAs:     {analysis['spa']['total']:>3}  │          │")
    print("└" + "─" * 68 + "┘")
    
    # Scores
    scores = analysis["scores"]
    print(f"\n📊 SCORES: Average {scores['average']:.1f}  |  Min {scores['min']}  |  Max {scores['max']}")
    
    # Performance
    perf = analysis["performance"]
    print(f"⚡ PERF:   Fast avg {perf['avg_fast_time']:.1f}s  |  Deep avg {perf['avg_deep_time']:.1f}s  |  Max {perf['max_deep_time']:.1f}s")
    
    # By Category
    print("\n📁 BY CATEGORY:")
    for cat, stats in analysis["by_category"].items():
        rate = 100 * stats["passed"] / stats["total"] if stats["total"] > 0 else 0
        emoji = "✅" if rate >= 80 else "⚠️" if rate >= 50 else "❌"
        print(f"   {emoji} {cat:15} {stats['passed']:>2}/{stats['total']:<2} ({rate:5.1f}%)")
    
    # By Complexity
    print("\n🎯 BY COMPLEXITY:")
    for comp, stats in analysis["by_complexity"].items():
        rate = 100 * stats["passed"] / stats["total"] if stats["total"] > 0 else 0
        emoji = "✅" if rate >= 80 else "⚠️" if rate >= 50 else "❌"
        print(f"   {emoji} {comp:10} {stats['passed']:>2}/{stats['total']:<2} ({rate:5.1f}%)")
    
    # SPA Detection
    if analysis["spa"]["total"] > 0:
        print(f"\n🔧 SPA FRAMEWORKS DETECTED ({analysis['spa']['total']} sites):")
        for fw, count in analysis["spa"]["frameworks"].items():
            print(f"   • {fw}: {count}")
    
    # Severity Breakdown
    print("\n🔍 ISSUE SEVERITY:")
    for sev, count in sorted(analysis["severity_breakdown"].items(), key=lambda x: -x[1]):
        bar = "█" * min(count // 5, 20)
        print(f"   {sev:12} {count:>4} {bar}")
    
    # Individual Results
    print("\n" + "─" * 70)
    print("  DETAILED RESULTS")
    print("─" * 70)
    
    for r in results:
        status = "✅" if r.passed else "❌" if r.error else "⚠️"
        spa_badge = f" [{r.spa_framework}]" if r.spa_framework else ""
        score_str = f"{r.deep_score:.0f}" if r.deep_score is not None else f"{r.fast_score:.0f}*" if r.fast_score is not None else "N/A"
        
        print(f"  {status} {r.site.name:25} Score: {score_str:>3} Issues: {r.deep_issues or r.fast_issues:>3} Time: {r.deep_time:.1f}s{spa_badge}")
        
        if r.error:
            print(f"      └─ Error: {r.error[:60]}...")
        elif r.degraded:
            print(f"      └─ ⚠️ Degraded mode triggered")
    
    # Recommendations
    print("\n" + "═" * 70)
    print("  💡 RECOMMENDATIONS")
    print("═" * 70)
    
    recommendations = []
    
    # Check for complex site failures
    complex_failures = [r for r in results if not r.passed and r.site.complexity == "complex" and not r.error]
    if complex_failures:
        recommendations.append({
            "priority": "HIGH",
            "area": "Complex Site Handling",
            "issue": f"{len(complex_failures)} complex sites failed score validation",
            "action": "Improve SPA hydration, Shadow DOM traversal, and dynamic content detection"
        })
    
    # Check for errors
    errors = [r for r in results if r.error]
    if errors:
        recommendations.append({
            "priority": "CRITICAL",
            "area": "Error Handling",
            "issue": f"{len(errors)} sites failed with errors",
            "action": "Review timeout handling, bot protection bypass, and error recovery"
        })
    
    # Check SPA issues
    spa_failures = [r for r in results if not r.passed and r.is_spa]
    if spa_failures:
        recommendations.append({
            "priority": "HIGH",
            "area": "SPA Support",
            "issue": f"{len(spa_failures)} SPA sites underperformed",
            "action": "Enhance framework-specific waiting and hydration detection"
        })
    
    for rec in recommendations:
        print(f"\n  [{rec['priority']}] {rec['area']}")
        print(f"    Issue:  {rec['issue']}")
        print(f"    Action: {rec['action']}")
    
    if not recommendations:
        print("\n  ✨ No critical issues! Engine is performing excellently.")
    
    print("\n" + "═" * 70)


def save_results(results: List[AuditResult], analysis: Dict[str, Any], filename: str = "batch_audit_results.json"):
    """Save results to JSON file."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "analysis": analysis,
        "results": [
            {
                "name": r.site.name,
                "url": r.site.url,
                "category": r.site.category,
                "complexity": r.site.complexity,
                "expected_range": [r.site.expected_score_min, r.site.expected_score_max],
                "fast_score": r.fast_score,
                "deep_score": r.deep_score,
                "fast_issues": r.fast_issues,
                "deep_issues": r.deep_issues,
                "fast_time": round(r.fast_time, 2),
                "deep_time": round(r.deep_time, 2),
                "passed": r.passed,
                "degraded": r.degraded,
                "error": r.error,
                "engines": r.engines_used,
                "wcag_criteria": r.wcag_criteria,
                "severity": r.severity_breakdown,
                "is_spa": r.is_spa,
                "spa_framework": r.spa_framework,
            }
            for r in results
        ]
    }
    
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n📄 Results saved to: {filepath}")
    return filepath


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def main():
    """Main entry point for batch testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="BEACON World-Class Batch Audit Test")
    parser.add_argument("--quick", type=int, help="Quick test with N sites")
    parser.add_argument("--category", type=str, help="Test only specific category")
    parser.add_argument("--parallel", type=int, default=2, help="Parallel execution count")
    parser.add_argument("--fast-only", action="store_true", help="Skip deep audits")
    args = parser.parse_args()
    
    # Select sites to test
    sites = WORLD_CLASS_TEST_SITES
    
    if args.category:
        sites = [s for s in sites if s.category == args.category]
        if not sites:
            print(f"No sites found for category: {args.category}")
            print(f"Available categories: {set(s.category for s in WORLD_CLASS_TEST_SITES)}")
            return
    
    if args.quick:
        # Pick diverse sites for quick test
        categories = list(set(s.category for s in sites))
        selected = []
        per_cat = max(1, args.quick // len(categories))
        for cat in categories:
            cat_sites = [s for s in sites if s.category == cat][:per_cat]
            selected.extend(cat_sites)
        sites = selected[:args.quick]
    
    print("\n" + "═" * 70)
    print("  🚀 BEACON WORLD-CLASS ACCESSIBILITY AUDIT")
    print("═" * 70)
    print(f"  Sites to test: {len(sites)}")
    print(f"  Parallel: {args.parallel}")
    print(f"  Mode: {'Fast only' if args.fast_only else 'Fast + Deep'}")
    print("═" * 70 + "\n")
    
    def progress(msg):
        print(f"  {msg}")
    
    start_time = time.time()
    results = await run_batch_audit(
        sites=sites,
        parallel=args.parallel,
        run_deep=not args.fast_only,
        progress_callback=progress
    )
    total_time = time.time() - start_time
    
    # Analyze and report
    analysis = analyze_results(results)
    print_report(results, analysis, total_time)
    save_results(results, analysis)


if __name__ == "__main__":
    asyncio.run(main())
