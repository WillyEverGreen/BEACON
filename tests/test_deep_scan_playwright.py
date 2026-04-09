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
from app.audit.failure_taxonomy import classify_failure_reason, normalize_reason


def _safe_avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _extract_quality_metrics(audit_result: dict) -> tuple[float, float]:
    rag_issues = [
        issue
        for issue in (audit_result.get("issues", []) or [])
        if bool(issue.get("rag_context"))
    ]
    if not rag_issues:
        return 0.0, 0.0

    issue_quality_scores: list[float] = []
    issue_acceptance_scores: list[float] = []

    for issue in rag_issues:
        quality = issue.get("quality_scores", {})
        if not isinstance(quality, dict):
            continue
        usefulness = float(quality.get("usefulness_score", 0.0) or 0.0)
        correctness = float(quality.get("correctness_score", 0.0) or 0.0)
        if usefulness > 0 or correctness > 0:
            issue_quality_scores.append((usefulness + correctness) / 2.0)

        predicted_acceptance = float(
            quality.get("predicted_acceptance_rate", quality.get("acceptance_rate", 0.0)) or 0.0
        )
        if predicted_acceptance > 0:
            issue_acceptance_scores.append(predicted_acceptance)

    meta_quality = ((audit_result.get("enrichment_meta") or {}).get("quality") or {})
    rag_effectiveness = _safe_avg(issue_quality_scores)
    if rag_effectiveness <= 0:
        rag_effectiveness = float(meta_quality.get("rag_effectiveness", 0.0) or 0.0)

    fix_acceptance_rate = _safe_avg(issue_acceptance_scores)
    if fix_acceptance_rate <= 0:
        fix_acceptance_rate = float(
            meta_quality.get("fix_acceptance_rate", meta_quality.get("acceptance_rate", 0.0)) or 0.0
        )

    return round(rag_effectiveness, 1), round(fix_acceptance_rate, 1)

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
    fast_rag_effectiveness: float = 0.0
    fast_fix_acceptance_rate: float = 0.0
    fast_enrichment_status: str = "off"
    fast_degraded: bool = False
    fast_degraded_reason: Optional[str] = None
    
    # Deep scan results
    deep_score: float = 0.0
    deep_issues: int = 0
    deep_time: float = 0.0
    deep_engines: list = field(default_factory=list)
    deep_rag_enriched: int = 0
    deep_rag_effectiveness: float = 0.0
    deep_fix_acceptance_rate: float = 0.0
    deep_enrichment_status: str = "off"
    deep_degraded: bool = False
    deep_degraded_reason: Optional[str] = None
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
                enable_enrichment=True,
                max_enrich_issues=20,        # ✅ RAG enabled
                enable_cognitive=False,      # ❌ No API calls
                await_enrichment=True,
            )
            result.fast_time = time.time() - fast_start
            result.fast_score = fast_result.get("score", 0)
            result.fast_issues = fast_result.get("total_issues", 0)
            result.fast_engines = fast_result.get("engines_used", [])
            result.fast_rag_enriched = sum(1 for iss in fast_result.get("issues", []) if iss.get("rag_context"))
            result.fast_rag_effectiveness, result.fast_fix_acceptance_rate = _extract_quality_metrics(fast_result)
            result.fast_enrichment_status = str(fast_result.get("enrichment_status", "off") or "off")
            result.fast_degraded = bool(fast_result.get("degraded_mode", False))
            result.fast_degraded_reason = fast_result.get("degraded_reason") or fast_result.get("degradation_reason")
            
            print(f"    ✓ Score: {result.fast_score:.1f}/100")
            print(f"    ✓ Issues: {result.fast_issues}")
            print(f"    ✓ Time: {result.fast_time:.1f}s")
            print(f"    ✓ Engines: {', '.join(result.fast_engines)}")
            print(f"    ✓ RAG enriched: {result.fast_rag_enriched} issues")
            print(f"    ✓ RAG effectiveness: {result.fast_rag_effectiveness:.1f}%")
            print(f"    ✓ Fix acceptance rate: {result.fast_fix_acceptance_rate:.1f}%")
            
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
                enable_enrichment=True,
                max_enrich_issues=20,        # ✅ RAG enabled
                enable_cognitive=False,      # ❌ No API calls
                await_enrichment=True,
            )
            result.deep_time = time.time() - deep_start
            result.deep_score = deep_result.get("score", 0)
            result.deep_issues = deep_result.get("total_issues", 0)
            result.deep_engines = deep_result.get("engines_used", [])
            result.deep_rag_enriched = sum(1 for iss in deep_result.get("issues", []) if iss.get("rag_context"))
            result.deep_rag_effectiveness, result.deep_fix_acceptance_rate = _extract_quality_metrics(deep_result)
            result.deep_enrichment_status = str(deep_result.get("enrichment_status", "off") or "off")
            result.deep_degraded = bool(deep_result.get("degraded_mode", False))
            result.deep_degraded_reason = deep_result.get("degraded_reason") or deep_result.get("degradation_reason")
            result.deep_spa_framework = deep_result.get("spa_framework")
            result.deep_is_spa = deep_result.get("is_spa", False)
            
            print(f"    ✓ Score: {result.deep_score:.1f}/100")
            print(f"    ✓ Issues: {result.deep_issues}")
            print(f"    ✓ Time: {result.deep_time:.1f}s")
            print(f"    ✓ Engines: {', '.join(result.deep_engines)}")
            print(f"    ✓ RAG enriched: {result.deep_rag_enriched} issues")
            print(f"    ✓ RAG effectiveness: {result.deep_rag_effectiveness:.1f}%")
            print(f"    ✓ Fix acceptance rate: {result.deep_fix_acceptance_rate:.1f}%")
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
            print(
                f"    RAG quality: {result.fast_rag_effectiveness:.1f}% → "
                f"{result.deep_rag_effectiveness:.1f}%"
            )
            
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
    
    completed = [r for r in results if not r.error]
    errors = [r for r in results if r.error]
    runtime_failures = [r for r in results if r.error or r.fast_degraded or r.deep_degraded]
    runtime_successes = [r for r in results if not r.error and not (r.fast_degraded or r.deep_degraded)]
    expectation_passes = [r for r in completed if r.met_expectations]
    spas_detected = [r for r in completed if r.deep_is_spa]
    rag_enriched = [r for r in completed if r.deep_rag_enriched > 0]
    degraded_count = sum(1 for r in results if r.fast_degraded or r.deep_degraded)
    timeout_count = sum(1 for r in errors if "timeout" in str(r.error).lower())

    def _p95(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = max(0, min(len(ordered) - 1, int(0.95 * (len(ordered) - 1))))
        return round(float(ordered[idx]), 2)

    fast_times = [r.fast_time for r in runtime_successes if r.fast_time >= 0]
    rag_terminal_statuses = {"complete", "failed", "skipped", "off"}
    rag_completed = sum(
        1
        for r in completed
        if str(r.deep_enrichment_status).strip().lower() in rag_terminal_statuses
    )
    rag_effectiveness_values = [r.deep_rag_effectiveness for r in completed if r.deep_rag_effectiveness > 0]
    fix_acceptance_values = [r.deep_fix_acceptance_rate for r in completed if r.deep_fix_acceptance_rate > 0]

    total_sites = len(STRATEGIC_SITES)
    runtime_success_rate = round((len(runtime_successes) / total_sites) * 100, 1)
    expectation_pass_rate = round((len(expectation_passes) / total_sites) * 100, 1)
    degraded_rate = round((degraded_count / len(STRATEGIC_SITES)) * 100, 1)
    timeout_rate = round((timeout_count / len(STRATEGIC_SITES)) * 100, 1)
    rag_completion_rate = round((rag_completed / len(completed)) * 100, 1) if completed else 0.0
    rag_effectiveness_rate = round(_safe_avg(rag_effectiveness_values), 1) if rag_effectiveness_values else 0.0
    fix_acceptance_rate = round(_safe_avg(fix_acceptance_values), 1) if fix_acceptance_values else 0.0
    avg_runtime = round(total_time / len(STRATEGIC_SITES), 2)
    fast_mode_usage = round((len(completed) / len(STRATEGIC_SITES)) * 100, 1)
    fast_mode_p95_time = _p95(fast_times)
    
    print(f"\n📋 Execution Summary:")
    print(f"  Total sites: 10")
    print(f"  Completed (no crash): {len(completed)}")
    print(f"  Runtime success: {len(runtime_successes)}/{total_sites} ({runtime_success_rate:.1f}%)")
    print(f"  Errors: {len(errors)}")
    print(f"  Met expectations: {len(expectation_passes)}/{total_sites} ({expectation_pass_rate:.1f}%)")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    
    if completed:
        # Overall metrics
        avg_fast_score = sum(r.fast_score for r in completed) / len(completed)
        avg_deep_score = sum(r.deep_score for r in completed) / len(completed)
        avg_improvement = sum(r.improvement_pct for r in completed) / len(completed)
        
        print(f"\n📈 Score Performance:")
        print(f"  Fast scan average: {avg_fast_score:.1f}/100")
        print(f"  Deep scan average: {avg_deep_score:.1f}/100")
        print(f"  Deep improvement: {avg_improvement:+.1f}% more issues found")
        
        # RAG effectiveness
        total_fast_rag = sum(r.fast_rag_enriched for r in completed)
        total_deep_rag = sum(r.deep_rag_enriched for r in completed)
        
        print(f"\n📚 RAG Enrichment Effectiveness:")
        print(f"  Sites with RAG data: {len(rag_enriched)}/10 ({100*len(rag_enriched)/len(completed):.0f}%)")
        print(f"  Fast scan enriched: {total_fast_rag} issues")
        print(f"  Deep scan enriched: {total_deep_rag} issues")
        print(f"  Average enrichment/site: {total_deep_rag/len(completed):.1f} issues")
        print(f"  RAG effectiveness: {rag_effectiveness_rate:.1f}%")
        print(f"  Fix acceptance rate: {fix_acceptance_rate:.1f}%")
        
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
        for r in completed:
            score_delta = r.deep_score - r.fast_score
            issues_str = f"{r.fast_issues}→{r.deep_issues}"
            spa_str = (r.deep_spa_framework or "No")[:8] if r.deep_is_spa else "No"
            met_str = "✅" if r.met_expectations else "⚠️"
            print(f"  {r.name:<15} {r.fast_score:>6.1f} {r.deep_score:>6.1f} {score_delta:>+6.1f} "
                  f"{issues_str:>7} {r.deep_rag_enriched:>5} {spa_str:<8} {met_str:<5}")
        
        # Purpose-specific insights
        print(f"\n🎯 Purpose-Specific Insights:")
        for r in completed:
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
    
    def _runtime_failure_type(row: StrategicResult) -> Optional[str]:
        if not (row.error or row.fast_degraded or row.deep_degraded):
            return None
        reason = normalize_reason(row.deep_degraded_reason or row.fast_degraded_reason) or classify_failure_reason(row.error)
        if reason in {"network_error", "blocked_request", "dns_failure"}:
            return reason
        return "network_error"

    failure_classification = []
    failure_breakdown = {
        "network_error": 0,
        "blocked_request": 0,
        "dns_failure": 0,
    }
    for r in results:
        if r.error or r.fast_degraded or r.deep_degraded:
            runtime_failure_type = _runtime_failure_type(r) or "network_error"
            failure_breakdown[runtime_failure_type] = failure_breakdown.get(runtime_failure_type, 0) + 1
            failure_classification.append(
                {
                    "name": r.name,
                    "url": r.url,
                    "failure_type": "runtime_failure",
                    "runtime_failure_type": runtime_failure_type,
                    "error": r.error,
                    "degraded": bool(r.fast_degraded or r.deep_degraded),
                    "degraded_reason": r.deep_degraded_reason or r.fast_degraded_reason,
                }
            )
        elif not r.met_expectations:
            failure_classification.append(
                {
                    "name": r.name,
                    "url": r.url,
                    "failure_type": "score_out_of_range",
                    "error": None,
                    "degraded": False,
                    "degraded_reason": None,
                }
            )

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
            "completed": len(completed),
            "runtime_successful": len(runtime_successes),
            "runtime_failed": len(runtime_failures),
            "errors": len(errors),
            "met_expectations": len(expectation_passes),
            "spas_detected": len(spas_detected),
            "rag_enriched_sites": len(rag_enriched)
        },
        "kpi": {
            "runtime_success_rate": runtime_success_rate,
            "expectation_pass_rate": expectation_pass_rate,
            "degraded_rate": degraded_rate,
            "precision": None,
            "recall": None,
            "f1": None,
            "spa_precision": None,
            "spa_recall": None,
            "rag_completion": rag_completion_rate,
            "rag_effectiveness": rag_effectiveness_rate,
            "fix_acceptance_rate": fix_acceptance_rate,
            "timeout_rate": timeout_rate,
            "avg_runtime": avg_runtime,
            "fast_mode_p95_time": fast_mode_p95_time,
            "fast_mode_usage": fast_mode_usage,
        },
        "failure_breakdown": failure_breakdown,
        "failure_classification": failure_classification,
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
                    "rag_enriched": r.fast_rag_enriched,
                    "rag_effectiveness": r.fast_rag_effectiveness,
                    "fix_acceptance_rate": r.fast_fix_acceptance_rate,
                    "enrichment_status": r.fast_enrichment_status,
                    "degraded": r.fast_degraded,
                    "degraded_reason": r.fast_degraded_reason,
                },
                "deep": {
                    "score": r.deep_score,
                    "issues": r.deep_issues,
                    "time": round(r.deep_time, 2),
                    "engines": r.deep_engines,
                    "rag_enriched": r.deep_rag_enriched,
                    "rag_effectiveness": r.deep_rag_effectiveness,
                    "fix_acceptance_rate": r.deep_fix_acceptance_rate,
                    "enrichment_status": r.deep_enrichment_status,
                    "degraded": r.deep_degraded,
                    "degraded_reason": r.deep_degraded_reason,
                    "spa_framework": r.deep_spa_framework,
                    "is_spa": r.deep_is_spa
                },
                "analysis": {
                    "improvement_pct": round(r.improvement_pct, 1),
                    "met_expectations": r.met_expectations,
                    "notes": r.notes
                },
                "failure_type": (
                    "runtime_failure"
                    if (r.error or r.fast_degraded or r.deep_degraded)
                    else ("score_out_of_range" if not r.met_expectations else None)
                ),
                "runtime_failure_type": (
                    _runtime_failure_type(r)
                    if (r.error or r.fast_degraded or r.deep_degraded)
                    else None
                ),
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
    
    if completed:
        expectation_hit_on_completed = (len(expectation_passes) / len(completed)) * 100

        if runtime_success_rate >= 90:
            print(f"  ✅ Runtime health: {runtime_success_rate:.0f}% runtime_success_rate")
        else:
            print(f"  ⚠️  Runtime health: {runtime_success_rate:.0f}% runtime_success_rate")

        if expectation_hit_on_completed >= 80:
            print(f"  ✅ EXCELLENT: {expectation_hit_on_completed:.0f}% of completed audits met expectations")
        elif expectation_hit_on_completed >= 60:
            print(f"  ✅ GOOD: {expectation_hit_on_completed:.0f}% of completed audits met expectations")
        else:
            print(f"  ⚠️  NEEDS WORK: Only {expectation_hit_on_completed:.0f}% of completed audits met expectations")
        
        if len(spas_detected) >= 3:
            print(f"  ✅ SPA Detection: Working ({len(spas_detected)} SPAs detected)")
        else:
            print(f"  ⚠️  SPA Detection: Weak ({len(spas_detected)} SPAs detected)")
        
        if len(rag_enriched) >= 7:
            print(f"  ✅ RAG Enrichment: Effective ({100*len(rag_enriched)/len(completed):.0f}% coverage)")
        elif len(rag_enriched) >= 4:
            print(f"  ⚠️  RAG Enrichment: Partial ({100*len(rag_enriched)/len(completed):.0f}% coverage)")
        else:
            print(f"  ❌ RAG Enrichment: Not working ({100*len(rag_enriched)/len(completed):.0f}% coverage)")

        if rag_effectiveness_rate >= 80:
            print(f"  ✅ RAG Effectiveness: {rag_effectiveness_rate:.1f}%")
        else:
            print(f"  ⚠️  RAG Effectiveness below target: {rag_effectiveness_rate:.1f}%")

        if fix_acceptance_rate >= 80:
            print(f"  ✅ Fix Acceptance Rate: {fix_acceptance_rate:.1f}%")
        else:
            print(f"  ⚠️  Fix Acceptance Rate below target: {fix_acceptance_rate:.1f}%")
        
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
