import json
from pathlib import Path

results_file = Path('evaluation/retest_act_latest.json')
if not results_file.exists():
    print(f"Error: {results_file} not found.")
    exit(1)

raw_data = json.load(results_file.open())
cases = raw_data.get('cases', [])

print(f"Total Cases: {len(cases)}")
fps_total = 0
rule_counts = {}

for case in cases:
    unexpected = case.get('unexpected_rule_ids', [])
    if unexpected:
        fps_total += len(unexpected)
        for rid in unexpected:
            rule_counts[rid] = rule_counts.get(rid, 0) + 1

print(f"Total False Positives in results: {fps_total}")
print("\nRules causing False Positives:")
for rid, count in sorted(rule_counts.items(), key=lambda x: x[1], reverse=True):
    print(f" - {rid}: {count} occurrences")
