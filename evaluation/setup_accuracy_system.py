#!/usr/bin/env python3
"""
Comprehensive accuracy system setup.
- Accept more low-confidence mappings
- Create adjudication templates
- Set up repeatable pipeline
"""

import json
from pathlib import Path
from collections import defaultdict


def accept_reasonable_lowconf_mappings():
    """Accept low-confidence mappings with multiple rule-type matches."""
    
    print("\n" + "="*70)
    print("STEP 1: ACCEPT LOW-CONFIDENCE MAPPINGS")
    print("="*70)
    
    with open('evaluation/act_rule_mapping.json') as f:
        existing = json.load(f) or {}
    
    with open('evaluation/act_mapping_low_confidence.json') as f:
        low_conf = json.load(f) or {}
    
    print(f"Current mapping: {len(existing)} entries")
    print(f"Low-confidence suggestions: {len(low_conf)} entries")
    
    accepted = 0
    rejected = 0
    
    for rule_id, suggestion in low_conf.items():
        suggested_ids = suggestion.get("suggested_internal_ids", [])
        
        if suggested_ids and rule_id not in existing:
            # Accept if single suggestion or matches known rule keywords
            known_keywords = {"aria", "video", "audio", "form", "button", "link", "image", "text", "heading", "lang", "contrast", "keyboard"}
            has_known = any(any(kw in id.lower() for kw in known_keywords) for id in suggested_ids)
            
            if len(suggested_ids) == 1 or has_known:
                existing[rule_id] = suggested_ids
                accepted += 1
                if accepted <= 10:
                    act_name = suggestion.get('act_name', '')[:45]
                    print(f"  [+] {rule_id}: {act_name}... -> {suggested_ids}")
            else:
                rejected += 1
    
    print(f"\nAccepted: {accepted} | Rejected: {rejected}")
    
    with open('evaluation/act_rule_mapping.json', 'w') as f:
        json.dump(existing, f, indent=2)
    
    print(f"Mapping saved: {len(existing)} total entries")
    return accepted, len(existing)


def create_adjudication_template():
    """Create template for manual labeling benchmark cases."""
    
    print("\n" + "="*70)
    print("STEP 2: CREATE ADJUDICATION TEMPLATE")
    print("="*70)
    
    with open('evaluation/benchmark_cases.json') as f:
        data = json.load(f)
    
    cases = data.get('cases', [])
    
    # Select diverse cases for labeling (one per rule type, sample of each)
    rule_examples = defaultdict(list)
    for case in cases:
        for rule in case.get('expected_rule_ids', []):
            if len(rule_examples[rule]) < 2:
                rule_examples[rule].append(case)
    
    template = {
        "instructions": [
            "For each case, verify if expected_rule_ids are correct",
            "If correct: set known_valid_rule_ids = expected_rule_ids",
            "If wrong: move incorrect ones to known_invalid_rule_ids",
            "If missing: add to expected_rule_ids and known_valid_rule_ids"
        ],
        "cases_to_label": []
    }
    
    labeled_count = 0
    for rule, examples in sorted(rule_examples.items())[:25]:
        if labeled_count >= 50:
            break
        case = examples[0]
        template["cases_to_label"].append({
            "name": case.get("name"),
            "url": case.get("url"),
            "expected_rule_ids": case.get("expected_rule_ids", []),
            "known_valid_rule_ids": [],
            "known_invalid_rule_ids": [],
        })
        labeled_count += 1
    
    with open('evaluation/adjudication_template.json', 'w') as f:
        json.dump(template, f, indent=2)
    
    print(f"Created adjudication template: {labeled_count} cases to label")
    return labeled_count


def run_full_benchmark():
    """Run full benchmark with current mapping."""
    
    print("\n" + "="*70)
    print("STEP 3: RUN FULL BENCHMARK")
    print("="*70)
    
    import subprocess
    
    # Rebuild benchmark
    print("Rebuilding benchmark...")
    subprocess.run([
        "python", "evaluation/ingest_benchmark_sources.py",
        "--sources", "evaluation/benchmark_sources.json",
        "--act-map", "evaluation/act_rule_mapping.json",
        "--out", "evaluation/benchmark_cases.json",
        "--report", "evaluation/benchmark_ingestion_report.json"
    ], check=True)
    
    # Run benchmark
    print("Running benchmark measurement...")
    subprocess.run([
        "python", "evaluation/benchmark_precision_recall.py",
        "evaluation/benchmark_cases.json",
        "--profile", "high_precision",
        "--scan-mode", "fast",
        "--out", "evaluation/benchmark_results_current.json"
    ], check=True)
    
    # Report results
    with open('evaluation/benchmark_results_current.json') as f:
        results = json.load(f)
    
    agg = results.get('aggregate', {})
    micro = agg.get('micro', {})
    
    print("\nBenchmark Results:")
    print(f"  Cases: {len(results.get('cases', []))}")
    print(f"  Micro Precision: {micro.get('precision', 0):.2%}")
    print(f"  Micro Recall: {micro.get('recall', 0):.2%}")
    print(f"  TP/FP/FN: {micro.get('tp', 0)}/{micro.get('fp', 0)}/{micro.get('fn', 0)}")
    
    return results


def main():
    print("\n" + "="*70)
    print("COMPREHENSIVE ACCURACY MEASUREMENT SYSTEM SETUP")
    print("="*70)
    
    try:
        # Step 1: Accept more mappings
        accepted, total = accept_reasonable_lowconf_mappings()
        
        # Step 2: Create adjudication template
        adj_cases = create_adjudication_template()
        
        # Step 3: Run full benchmark
        results = run_full_benchmark()
        
        print("\n" + "="*70)
        print("SYSTEM READY")
        print("="*70)
        print("\nNext Steps:")
        print("1. Manually review evaluation/adjudication_template.json")
        print("2. Update known_valid_rule_ids and known_invalid_rule_ids")
        print("3. Run: python evaluation/apply_adjudication.py")
        print("4. Re-run benchmark to measure true precision/recall")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
