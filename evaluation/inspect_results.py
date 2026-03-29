#!/usr/bin/env python3
import json

with open('evaluation/benchmark_results_expanded.json') as f:
    results = json.load(f)

print('Benchmark Results Summary:')
print(f"  Cases scanned: {len(results['cases'])}")
labeled = sum(1 for c in results['cases'] if c.get('known_valid_rule_ids') or c.get('known_invalid_rule_ids'))
print(f"  Labeled cases: {labeled}")
print(f"  Unlabeled cases: {len(results['cases']) - labeled}")

print(f"\nMetrics:")
print(f"  Micro Precision: {results['metrics']['precision']:.2f}%")
print(f"  Micro Recall: {results['metrics']['recall']:.2f}%")
adj = results.get('adjudicated_metrics', {})
print(f"  Adjudicated Precision: {adj.get('precision', 0):.2f}%")
print(f"  Adjudicated Recall: {adj.get('recall', 0):.2f}%")

print(f"\nKey Stats:")
print(f"  TP/FP/FN: {results['metrics'].get('tp', 0)}/{results['metrics'].get('fp', 0)}/{results['metrics'].get('fn', 0)}")
print(f"  Adj TP/FP/FN: {adj.get('tp', 0)}/{adj.get('fp', 0)}/{adj.get('fn', 0)}")
