#!/usr/bin/env python3
"""
Analyze benchmark results to guide detection improvements.
Identifies patterns in false positives and false negatives.
"""

import json
from collections import defaultdict


def analyze_results():
    """Analyze benchmark results for improvement opportunities."""
    
    with open('evaluation/benchmark_results_current.json') as f:
        results = json.load(f)
    
    print("="*70)
    print("BENCHMARK ANALYSIS")
    print("="*70)
    
    cases = results.get('cases', [])
    agg = results.get('aggregate', {})
    micro = agg.get('micro', {})
    
    print(f"\nOverall Metrics:")
    print(f"  Cases: {len(cases)}")
    print(f"  Precision: {micro.get('precision', 0):.2%}")
    print(f"  Recall: {micro.get('recall', 0):.2%}")
    print(f"  TP/FP/FN: {micro.get('tp', 0)}/{micro.get('fp', 0)}/{micro.get('fn', 0)}")
    
    # Analyze false positives
    fp_by_rule = defaultdict(int)
    tp_by_rule = defaultdict(int)
    fn_by_rule = defaultdict(int)
    
    for case in cases:
        expected = set(case.get('expected_rule_ids', []))
        predicted = set(case.get('predicted_rule_ids', []))
        unexpected = case.get('unexpected_rule_ids', [])
        missing = case.get('missing_rule_ids', [])
        
        for rule in predicted:
            if rule in expected:
                tp_by_rule[rule] += 1
            else:
                fp_by_rule[rule] += 1
        
        for rule in missing:
            fn_by_rule[rule] += 1
    
    print("\n" + "="*70)
    print("FALSE POSITIVES (Rules we report but shouldn't)")
    print("="*70)
    
    top_fp = sorted(fp_by_rule.items(), key=lambda x: x[1], reverse=True)[:15]
    for rule, count in top_fp:
        print(f"  {rule}: {count} occurrences")
    
    print("\n" + "="*70)
    print("FALSE NEGATIVES (Rules we miss)")
    print("="*70)
    
    top_fn = sorted(fn_by_rule.items(), key=lambda x: x[1], reverse=True)[:15]
    for rule, count in top_fn:
        print(f"  {rule}: {count} occurrences")
    
    print("\n" + "="*70)
    print("TRUE POSITIVES (Rules we get right)")
    print("="*70)
    
    top_tp = sorted(tp_by_rule.items(), key=lambda x: x[1], reverse=True)[:10]
    for rule, count in top_tp:
        print(f"  {rule}: {count} correct detections")
    
    # Recommend profile tuning
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    
    total_fp = micro.get('fp', 0)
    total_tp = micro.get('tp', 0)
    total_fn = micro.get('fn', 0)
    
    if total_fp > total_tp * 10:
        print("\n[CRITICAL] Precision is very low (2%)")
        print("  Action: High-precision profile too aggressive in reporting")
        print("  Solution: Increase confidence threshold or disable low-confidence rules")
        print("  - Many rules firing on same issue (duplicate detection)")
        print("  - Consider: Disable cognitive/contextual checks temporarily")
    
    if total_fn > 0:
        fn_pct = total_fn / (total_tp + total_fn) * 100
        print(f"\n[HIGH RECALL GAP] Missing {fn_pct:.1f}% of issues")
        print("  Top missing rules should be investigated")
        print("  Solutions:")
        print("    1. Check if detection engines are enabled (static, heuristic, browser)")
        print("    2. Verify rule mapping is complete")
        print("    3. Consider enabling cognitive checks for contextual rules")
    
    # Save analysis
    analysis = {
        "summary": {
            "cases": len(cases),
            "precision": micro.get('precision', 0),
            "recall": micro.get('recall', 0),
            "tp": micro.get('tp', 0),
            "fp": micro.get('fp', 0),
            "fn": micro.get('fn', 0),
        },
        "false_positives": dict(top_fp),
        "false_negatives": dict(top_fn),
        "true_positives": dict(top_tp),
    }
    
    with open('evaluation/analysis_current.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\nAnalysis saved: evaluation/analysis_current.json")


if __name__ == "__main__":
    analyze_results()
