"""
Comprehensive real-site test — runs BEACON engine against a live URL
and produces a detailed analysis report.
"""
import asyncio
import json
import sys
import os
import time
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from app.services.audit_runner import run_audit


async def run_comprehensive_test(url: str):
    """Run both fast and deep scans, then produce detailed analysis."""
    
    print(f"\n{'='*80}")
    print(f"  BEACON ENGINE — COMPREHENSIVE REAL-SITE TEST")
    print(f"  Target: {url}")
    print(f"{'='*80}\n")
    
    # ── FAST MODE SCAN ────────────────────────────────────────
    print("▶ Running FAST mode scan (static + heuristic engines)...")
    fast_result = await run_audit(
        url,
        scan_mode="fast",
        precision_profile="balanced",
        enable_enrichment=False,  # Skip LLM to avoid API key issues
        enable_cognitive=False,
    )
    
    print(f"\n{'─'*60}")
    print(f"  FAST SCAN RESULTS")
    print(f"{'─'*60}")
    print(f"  Score:        {fast_result.get('score', 'N/A')}/100")
    print(f"  Total Issues: {fast_result.get('total_issues', 0)}")
    print(f"  Engines:      {', '.join(fast_result.get('engines_used', []))}")
    print(f"  Scan Time:    {fast_result.get('scan_time_seconds', 0):.2f}s")
    
    # Quality gates
    qg = fast_result.get("quality_gates", {})
    print(f"\n  Quality Gates:")
    print(f"    Runtime:    {qg.get('runtime_actual', '?')}s / {qg.get('runtime_limit', '?')}s {'✅' if qg.get('runtime_passed') else '❌'}")
    print(f"    Pre-dedup:  {qg.get('total_before_dedup', '?')} issues")
    print(f"    Post-dedup: {qg.get('total_after_dedup', '?')} issues")
    if 'duplicate_rate' in qg:
        print(f"    Dup Rate:   {qg['duplicate_rate']*100:.1f}% {'✅' if qg.get('duplicate_rate_passed') else '❌'}")
    
    # Precision profile telemetry
    pt = fast_result.get("precision_profile_telemetry", {})
    if pt:
        print(f"\n  Precision Filter:")
        print(f"    Profile:    {pt.get('profile', '?')}")
        print(f"    Input:      {pt.get('input_issues', '?')}")
        print(f"    Reported:   {pt.get('reported_issues', '?')}")
        print(f"    Dropped (low conf):   {pt.get('dropped_low_confidence', 0)}")
        print(f"    Dropped (needs rev):  {pt.get('dropped_needs_review', 0)}")
        print(f"    Dropped (contextual): {pt.get('dropped_contextual_single_source', 0)}")
    
    # Issue breakdown
    issues = fast_result.get("issues", [])
    if issues:
        # By severity
        sev_counts = {}
        for i in issues:
            sev = i.get("severity", "unknown")
            sev_counts[sev] = sev_counts.get(sev, 0) + 1
        
        print(f"\n  Issues by Severity:")
        for sev in ["critical", "serious", "moderate", "minor"]:
            count = sev_counts.get(sev, 0)
            if count:
                bar = "█" * min(count, 40)
                print(f"    {sev:10s}: {count:3d} {bar}")
        
        # By confidence tier
        tier_counts = {}
        for i in issues:
            tier = i.get("confidence_tier", "unknown")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        print(f"\n  Issues by Confidence:")
        for tier in ["high", "medium", "low"]:
            count = tier_counts.get(tier, 0)
            if count:
                print(f"    {tier:10s}: {count:3d}")
        
        # By source
        source_counts = {}
        for i in issues:
            src = i.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
        
        print(f"\n  Issues by Source:")
        for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            print(f"    {src:15s}: {count:3d}")
        
        # WCAG coverage
        wcag_scs = set()
        for i in issues:
            sc = i.get("wcag_criterion", "")
            if sc:
                wcag_scs.add(sc)
        
        print(f"\n  WCAG Coverage: {len(wcag_scs)} unique criteria referenced")
        if wcag_scs:
            print(f"    {', '.join(sorted(wcag_scs))}")
        
        # Avg confidence
        confs = [i.get("confidence", 0) for i in issues]
        avg_conf = sum(confs) / len(confs) if confs else 0
        print(f"\n  Average Confidence: {avg_conf:.3f}")
        
        # Detailed issue listing (top 25)
        print(f"\n{'─'*60}")
        print(f"  TOP ISSUES (sorted by severity & confidence)")
        print(f"{'─'*60}")
        
        sev_order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
        sorted_issues = sorted(
            issues, 
            key=lambda x: (sev_order.get(x.get("severity", "minor"), 4), -x.get("confidence", 0))
        )
        
        for idx, issue in enumerate(sorted_issues[:25], 1):
            sev = issue.get("severity", "?")
            conf = issue.get("confidence", 0)
            rule = issue.get("rule_id", "unknown")
            desc = issue.get("description", "")[:80]
            wcag = issue.get("wcag_criterion", "")
            tier = issue.get("confidence_tier", "?")
            src = issue.get("source", "?")
            review = "⚠️REVIEW" if issue.get("needs_manual_review") else ""
            
            print(f"\n  [{idx:2d}] {sev.upper():10s} | conf={conf:.2f} ({tier}) | {rule}")
            print(f"       {desc}")
            if wcag:
                print(f"       WCAG: {wcag} | Source: {src} {review}")
            
            element = issue.get("element", "")
            if element:
                print(f"       Element: {element[:80]}")
    
    # Groups analysis
    groups = fast_result.get("groups", [])
    if groups:
        print(f"\n{'─'*60}")
        print(f"  ISSUE GROUPS ({len(groups)} groups)")
        print(f"{'─'*60}")
        for g in groups[:10]:
            print(f"  • {g.get('category', '?')} ({g.get('count', 0)} issues) — {g.get('description', '')[:60]}")
    
    # ── DEEP MODE SCAN ────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print(f"▶ Running DEEP mode scan (+ browser probes, axe-core, cognitive)...")
    print(f"{'='*60}")
    
    deep_result = await run_audit(
        url,
        scan_mode="deep",
        precision_profile="balanced",
        enable_enrichment=False,
        enable_cognitive=True,
    )
    
    print(f"\n  DEEP SCAN RESULTS")
    print(f"  Score:        {deep_result.get('score', 'N/A')}/100")
    print(f"  Total Issues: {deep_result.get('total_issues', 0)}")
    print(f"  Engines:      {', '.join(deep_result.get('engines_used', []))}")
    print(f"  Scan Time:    {deep_result.get('scan_time_seconds', 0):.2f}s")
    
    # Cognitive scores
    cog = deep_result.get("cognitive_scores", {})
    if cog:
        print(f"\n  Cognitive Analysis:")
        for key, val in cog.items():
            if isinstance(val, (int, float)):
                print(f"    {key:30s}: {val}")
    
    deep_issues = deep_result.get("issues", [])
    deep_sev = {}
    for i in deep_issues:
        sev = i.get("severity", "unknown")
        deep_sev[sev] = deep_sev.get(sev, 0) + 1
    
    if deep_sev:
        print(f"\n  Deep Issues by Severity:")
        for sev in ["critical", "serious", "moderate", "minor"]:
            count = deep_sev.get(sev, 0)
            if count:
                print(f"    {sev:10s}: {count:3d}")
    
    # New issues found by deep that fast missed
    fast_rules = {i.get("rule_id") for i in issues}
    deep_only = [i for i in deep_issues if i.get("rule_id") not in fast_rules]
    if deep_only:
        print(f"\n  Deep-only findings ({len(deep_only)} new):")
        for i in deep_only[:10]:
            print(f"    • [{i.get('severity','?')}] {i.get('rule_id','?')}: {i.get('description','')[:60]}")
    
    # ── FINAL VERDICT ─────────────────────────────────────────
    print(f"\n\n{'='*80}")
    print(f"  FINAL ENGINE VERDICT")
    print(f"{'='*80}")
    print(f"  URL:               {url}")
    print(f"  Fast Score:        {fast_result.get('score', 0)}/100 ({fast_result.get('total_issues', 0)} issues in {fast_result.get('scan_time_seconds', 0):.1f}s)")
    print(f"  Deep Score:        {deep_result.get('score', 0)}/100 ({deep_result.get('total_issues', 0)} issues in {deep_result.get('scan_time_seconds', 0):.1f}s)")
    print(f"  Engine Coverage:   {', '.join(set(fast_result.get('engines_used', []) + deep_result.get('engines_used', [])))}")
    print(f"  WCAG SCs Hit:      {len(wcag_scs)}")
    
    # Engine quality metrics
    all_issues = fast_result.get("issues", [])
    high_conf = sum(1 for i in all_issues if i.get("confidence", 0) >= 0.85)
    med_conf = sum(1 for i in all_issues if 0.6 <= i.get("confidence", 0) < 0.85)
    low_conf = sum(1 for i in all_issues if i.get("confidence", 0) < 0.6)
    
    print(f"  Confidence Split:  {high_conf} high / {med_conf} medium / {low_conf} low")
    print(f"  Avg Confidence:    {avg_conf:.3f}")
    print(f"{'='*80}\n")
    
    # Save full results
    report = {
        "target": url,
        "fast_scan": fast_result,
        "deep_scan": deep_result,
        "analysis": {
            "wcag_criteria_hit": sorted(list(wcag_scs)),
            "severity_distribution": sev_counts,
            "avg_confidence": round(avg_conf, 3),
            "confidence_distribution": tier_counts,
        }
    }
    
    out_path = os.path.join(os.path.dirname(__file__), "sugarlabs_audit_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"  Full report saved to: {out_path}")
    
    return report


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.sugarlabs.org/"
    asyncio.run(run_comprehensive_test(url))
