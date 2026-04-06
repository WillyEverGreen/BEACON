#!/usr/bin/env python3
"""
Strategic 10-Site Accessibility Test - Fast vs Deep with RAG
=============================================================
Hand-picked sites that test specific aspects of your engine:

1. apple.com         - Near-perfect baseline (false positive detection)
2. wikipedia.org     - Rich semantic HTML (should score high)
3. twitter.com       - SPA with dynamic content (JS rendering test)
4. gov.uk           - Gold standard accessibility (scoring validation)
5. amazon.com        - Complex, real issues (detection capability)
6. reddit.com        - SPA infinite scroll (dynamic landmark detection)
7. nytimes.com       - Paywalls/overlays (interrupted flow handling)
8. craigslist.org    - Old-school HTML (semantic simplicity)
9. web.dev           - Google's a11y site (should score very high)
10. facebook.com     - Obfuscated SPA (stress test)

Config: RAG ENABLED, Cognitive DISABLED (save API costs)
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.audit_runner import run_audit

# Strategic test sites with their testing purpose
STRATEGIC_SITES = [
    {
        "url": "https://www.apple.com/",
        "name": "Apple",
        "category": "tech",
        "purpose": "Near-perfect accessibility — baseline for false positive detection",
        "expected": "Should score 85-95 with minimal issues"
    },
    {
        "url": "https://www.wikipedia.org/",
        "name": "Wikipedia",
        "category": "education",
        "purpose": "Rich semantic HTML with proper landmarks and headings",
        "expected": "Should score 90+ due to excellent semantic structure"
    },
    {
        "url": "https://twitter.com/",
        "name": "Twitter/X",
        "category": "social",
        "purpose": "Notorious SPA with dynamic content — tests JS rendering",
        "expected": "Should detect as React SPA, handle dynamic content"
    },
    {
        "url": "https://www.gov.uk/",
        "name": "GOV.UK",
        "category": "government",
        "purpose": "Gold standard in accessibility — validates scoring scale",
        "expected": "Should score 95+ as accessibility benchmark"
    },
    {
        "url": "https://www.amazon.com/",
        "name": "Amazon",
        "category": "ecommerce",
        "purpose": "Complex, ad-heavy, mixed accessibility — real issues",
        "expected": "Should find 15-30 real issues, score 60-75"
    },
    {
        "url": "https://www.reddit.com/",
        "name": "Reddit",
        "category": "social",
        "purpose": "SPA with infinite scroll — dynamic landmark detection",
        "expected": "Should handle dynamic loading, detect as React SPA"
    },
    {
        "url": "https://www.nytimes.com/",
        "name": "NY Times",
        "category": "news",
        "purpose": "Paywalls, overlays, modals — interrupted flow handling",
        "expected": "Should handle overlays gracefully, find modal issues"
    },
    {
        "url": "https://www.craigslist.org/",
        "name": "Craigslist",
        "category": "blog",
        "purpose": "Old-school HTML, no JS — semantic simplicity test",
        "expected": "Should score well (80-90), fast scan sufficient"
    },
    {
        "url": "https://web.dev/",
        "name": "web.dev",
        "category": "education",
        "purpose": "Google's accessibility-focused dev site — high bar",
        "expected": "Should score 90-95+, minimal issues"
    },
    {
        "url": "https://www.facebook.com/",
        "name": "Facebook",
        "category": "social",
        "purpose": "Heavily obfuscated SPA — stress test for false positives",
        "expected": "Should detect as React SPA, avoid false positives"
    },
]

@dataclass
class StrategicResult:
    """Result from testing one strategic site."""
    name: str
    url: str
    purpose: str
    expected: str
    
    # Fast scan results
    fast_score: float = 0.0
    fast_issues: int = 0
    fast_time: float = 0.0
    fast_engines: list = field(default_factory=list)
    fast_rag_enriched: int = 0
    
    # Deep scan results
    deep_score: float = 0.0
    deep_issues: int = 0
    deep_time: float = 0.0
    deep_engines: list = field(default_factory=list)
    deep_rag_enriched: int = 0
    deep_spa_framework: Optional[str] = None
    deep_is_spa: bool = False
    
    # Comparison
    improvement_pct: float = 0.0
    met_expectations: bool = False
    notes: str = ""
    error: Optional[str] = None

async def test_strategic_site(site_data: dict, semaphore) -> StrategicResult:
    """Test one strategic site with both Fast and Deep scans (RAG enabled)."""
    async with semaphore:
        result = StrategicResult(
            name=site_data["name"],
            url=site_data["url"],
            purpose=site_data["purpose"],
            expected=site_data["expected"]
        )
        
        print("\n" + "="*80)
        print(f"  🎯 {result.name}")
        print("="*80)
        print(f"  Purpose: {result.purpose}")
        print(f"  Expected: {result.expected}")
        print("-"*80)
        
        # ========================================================================
        # FAST SCAN (with RAG, no Cognitive)
        # ========================================================================
        print(f"  [1/2] FAST scan (RAG enabled, no API)...", flush=True)
        fast_start = time.time()
        try:
            fast_result = await run_audit(
                url=site_data["url"],
                scan_mode="fast",
                precision_profile="balanced",
                max_enrich_issues=20,        # ✅ RAG enabled
                enable_cognitive=False       # ❌ No API calls
            )
            result.fast_time = time.time() - fast_start
            result.fast_score = fast_result.get("score", 0)
            result.fast_issues = fast_result.get("total_issues", 0)
            result.fast_engines = fast_result.get("engines_used", [])
            result.fast_rag_enriched = sum(1 for iss in fast_result.get("issues", []) if iss.get("rag_context"))
            
            print(f"    ✓ Score: {result.fast_score:.1f}/100")
            print(f"    ✓ Issues: {result.fast_issues}")
            print(f"    ✓ Time: {result.fast_time:.1f}s")
            print(f"    ✓ Engines: {', '.join(result.fast_engines)}")
            print(f"    ✓ RAG enriched: {result.fast_rag_enriched} issues")
            
        except Exception as e:
            result.error = f"Fast scan failed: {str(e)[:150]}"
            print(f"    ✗ Error: {str(e)[:80]}")
            return result
        
        # ========================================================================
        # DEEP SCAN (with RAG, no Cognitive)
        # ========================================================================
        print(f"\n  [2/2] DEEP scan (RAG enabled, no API)...", flush=True)
        deep_start = time.time()
        try:
            deep_result = await run_audit(
                url=site_data["url"],
                scan_mode="deep",
                precision_profile="balanced",
                max_enrich_issues=20,        # ✅ RAG enabled
                enable_cognitive=False       # ❌ No API calls
            )
            result.deep_time = time.time() - deep_start
            result.deep_score = deep_result.get("score", 0)
            result.deep_issues = deep_result.get("total_issues", 0)
            result.deep_engines = deep_result.get("engines_used", [])
            result.deep_rag_enriched = sum(1 for iss in deep_result.get("issues", []) if iss.get("rag_context"))
            result.deep_spa_framework = deep_result.get("spa_framework")
            result.deep_is_spa = deep_result.get("is_spa", False)
            
            print(f"    ✓ Score: {result.deep_score:.1f}/100")
            print(f"    ✓ Issues: {result.deep_issues}")
            print(f"    ✓ Time: {result.deep_time:.1f}s")
            print(f"    ✓ Engines: {', '.join(result.deep_engines)}")
            print(f"    ✓ RAG enriched: {result.deep_rag_enriched} issues")
            if result.deep_is_spa:
                print(f"    ✓ SPA detected: {result.deep_spa_framework or 'Unknown framework'}")
            
        except Exception as e:
            result.error = f"Deep scan failed: {str(e)[:150]}"
            print(f"    ✗ Error: {str(e)[:80]}")
        
        # ========================================================================
        # ANALYSIS
        # ========================================================================
        if not result.error:
            result.improvement_pct = ((result.deep_issues - result.fast_issues) / result.fast_issues * 100) if result.fast_issues > 0 else 0
            
            print(f"\n  📊 Analysis:")
            print(f"    Fast → Deep: {result.fast_score:.1f} → {result.deep_score:.1f} ({result.deep_score - result.fast_score:+.1f})")
            print(f"    Issues found: {result.fast_issues} → {result.deep_issues} ({result.improvement_pct:+.1f}%)")
            print(f"    Speed: {result.fast_time:.1f}s → {result.deep_time:.1f}s ({result.deep_time/result.fast_time:.1f}x)")
            print(f"    RAG impact: {result.fast_rag_enriched} → {result.deep_rag_enriched} enriched issues")
            
            # Check if met expectations (basic heuristic)
            if "90+" in result.expected or "95+" in result.expected:
                result.met_expectations = result.deep_score >= 90
            elif "85-95" in result.expected:
                result.met_expectations = 85 <= result.deep_score <= 95
            elif "80-90" in result.expected:
                result.met_expectations = 80 <= result.deep_score <= 90
            else:
                result.met_expectations = True  # No specific expectation
            
            status = "✅ MET" if result.met_expectations else "⚠️ MISSED"
            print(f"    Expectations: {status}")
        
        return result

async def main():
    print("\n" + "="*80)
    print("  🎯 STRATEGIC 10-SITE ACCESSIBILITY TEST")
    print("  Hand-picked sites testing specific engine capabilities")
    print("  Config: RAG ENABLED, Cognitive DISABLED (cost-saving)")
    print("="*80)
    
    start_time = time.time()
    
    # Run tests with controlled parallelism (2 concurrent)
    semaphore = asyncio.Semaphore(2)
    tasks = []
    
    for i, site_data in enumerate(STRATEGIC_SITES, 1):
        print(f"\n[{i}/10] Queuing: {site_data['name']}")
        task = test_strategic_site(site_data, semaphore)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    # ============================================================================
    # COMPREHENSIVE ANALYSIS
    # ============================================================================
    
    print("\n\n" + "="*80)
    print("  📊 STRATEGIC TEST RESULTS & ANALYSIS")
    print("="*80)
    
    successful = [r for r in results if not r.error]
    errors = [r for r in results if r.error]
    met_expectations = [r for r in successful if r.met_expectations]
    spas_detected = [r for r in successful if r.deep_is_spa]
    rag_enriched = [r for r in successful if r.deep_rag_enriched > 0]
    
    print(f"\n📋 Execution Summary:")
    print(f"  Total sites: 10")
    print(f"  Successful: {len(successful)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Met expectations: {len(met_expectations)}/{len(successful)} ({100*len(met_expectations)/len(successful):.0f}%)")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    
    if successful:
        # Overall metrics
        avg_fast_score = sum(r.fast_score for r in successful) / len(successful)
        avg_deep_score = sum(r.deep_score for r in successful) / len(successful)
        avg_improvement = sum(r.improvement_pct for r in successful) / len(successful)
        
        print(f"\n📈 Score Performance:")
        print(f"  Fast scan average: {avg_fast_score:.1f}/100")
        print(f"  Deep scan average: {avg_deep_score:.1f}/100")
        print(f"  Deep improvement: {avg_improvement:+.1f}% more issues found")
        
        # RAG effectiveness
        total_fast_rag = sum(r.fast_rag_enriched for r in successful)
        total_deep_rag = sum(r.deep_rag_enriched for r in successful)
        
        print(f"\n📚 RAG Enrichment Effectiveness:")
        print(f"  Sites with RAG data: {len(rag_enriched)}/10 ({100*len(rag_enriched)/len(successful):.0f}%)")
        print(f"  Fast scan enriched: {total_fast_rag} issues")
        print(f"  Deep scan enriched: {total_deep_rag} issues")
        print(f"  Average enrichment/site: {total_deep_rag/len(successful):.1f} issues")
        
        # SPA detection
        if spas_detected:
            print(f"\n🔧 SPA Detection:")
            print(f"  SPAs detected: {len(spas_detected)}/10")
            for r in spas_detected:
                fw = r.deep_spa_framework or "Unknown"
                print(f"    - {r.name}: {fw}")
        
        # Detailed results
        print(f"\n📊 Detailed Site-by-Site Results:")
        print(f"  {'Site':<15} {'Fast':>6} {'Deep':>6} {'Δ':>6} {'Issues':>7} {'RAG':>5} {'SPA':<8} {'Met?':<5}")
        print(f"  {'-'*70}")
        for r in successful:
            score_delta = r.deep_score - r.fast_score
            issues_str = f"{r.fast_issues}→{r.deep_issues}"
            spa_str = (r.deep_spa_framework or "No")[:8] if r.deep_is_spa else "No"
            met_str = "✅" if r.met_expectations else "⚠️"
            print(f"  {r.name:<15} {r.fast_score:>6.1f} {r.deep_score:>6.1f} {score_delta:>+6.1f} "
                  f"{issues_str:>7} {r.deep_rag_enriched:>5} {spa_str:<8} {met_str:<5}")
        
        # Purpose-specific insights
        print(f"\n🎯 Purpose-Specific Insights:")
        for r in successful:
            status = "✅" if r.met_expectations else "⚠️"
            print(f"\n  {status} {r.name}:")
            print(f"     Purpose: {r.purpose}")
            print(f"     Result: Deep scan scored {r.deep_score:.1f}, found {r.deep_issues} issues")
            if r.deep_is_spa:
                print(f"     SPA: Detected as {r.deep_spa_framework or 'Unknown framework'}")
            if r.deep_rag_enriched > 0:
                print(f"     RAG: {r.deep_rag_enriched} issues enriched with knowledge")
    
    # ============================================================================
    # SAVE RESULTS
    # ============================================================================
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_time": round(total_time, 2),
        "configuration": {
            "scan_modes": ["fast", "deep"],
            "rag_enabled": True,
            "cognitive_enabled": False,
            "max_enrich_issues": 20
        },
        "summary": {
            "total_sites": 10,
            "successful": len(successful),
            "errors": len(errors),
            "met_expectations": len(met_expectations),
            "spas_detected": len(spas_detected),
            "rag_enriched_sites": len(rag_enriched)
        },
        "results": [
            {
                "name": r.name,
                "url": r.url,
                "purpose": r.purpose,
                "expected": r.expected,
                "fast": {
                    "score": r.fast_score,
                    "issues": r.fast_issues,
                    "time": round(r.fast_time, 2),
                    "engines": r.fast_engines,
                    "rag_enriched": r.fast_rag_enriched
                },
                "deep": {
                    "score": r.deep_score,
                    "issues": r.deep_issues,
                    "time": round(r.deep_time, 2),
                    "engines": r.deep_engines,
                    "rag_enriched": r.deep_rag_enriched,
                    "spa_framework": r.deep_spa_framework,
                    "is_spa": r.deep_is_spa
                },
                "analysis": {
                    "improvement_pct": round(r.improvement_pct, 1),
                    "met_expectations": r.met_expectations,
                    "notes": r.notes
                },
                "error": r.error
            }
            for r in results
        ]
    }
    
    output_file = "tests/strategic_10_site_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\n💾 Results saved to: {output_file}")
    
    # ============================================================================
    # FINAL VERDICT
    # ============================================================================
    
    print("\n" + "="*80)
    print("  🏆 FINAL VERDICT")
    print("="*80)
    
    if successful:
        success_rate = len(met_expectations) / len(successful) * 100
        
        if success_rate >= 80:
            print(f"  ✅ EXCELLENT: {success_rate:.0f}% of sites met expectations")
        elif success_rate >= 60:
            print(f"  ✅ GOOD: {success_rate:.0f}% of sites met expectations")
        else:
            print(f"  ⚠️  NEEDS WORK: Only {success_rate:.0f}% of sites met expectations")
        
        if len(spas_detected) >= 3:
            print(f"  ✅ SPA Detection: Working ({len(spas_detected)} SPAs detected)")
        else:
            print(f"  ⚠️  SPA Detection: Weak ({len(spas_detected)} SPAs detected)")
        
        if len(rag_enriched) >= 7:
            print(f"  ✅ RAG Enrichment: Effective ({100*len(rag_enriched)/len(successful):.0f}% coverage)")
        elif len(rag_enriched) >= 4:
            print(f"  ⚠️  RAG Enrichment: Partial ({100*len(rag_enriched)/len(successful):.0f}% coverage)")
        else:
            print(f"  ❌ RAG Enrichment: Not working ({100*len(rag_enriched)/len(successful):.0f}% coverage)")
        
        if avg_improvement > 40:
            print(f"  ✅ Deep vs Fast: Deep scan finds {avg_improvement:.0f}% more issues")
        elif avg_improvement > 20:
            print(f"  ✅ Deep vs Fast: Deep scan finds {avg_improvement:.0f}% more issues")
        else:
            print(f"  ⚠️  Deep vs Fast: Only {avg_improvement:.0f}% improvement")
    
    print("\n" + "="*80)
    print("  ✅ STRATEGIC TEST COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
