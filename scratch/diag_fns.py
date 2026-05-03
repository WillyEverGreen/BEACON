import json
from pathlib import Path

results_file = Path('evaluation/retest_act_latest.json')
if not results_file.exists():
    print(f"Error: {results_file} not found.")
    exit(1)

raw_data = json.load(results_file.open())
cases = raw_data.get('cases', [])

print(f"Total Cases: {len(cases)}")
fns_total = 0
missing_rules = {}

for case in cases:
    missing = case.get('missing_rule_ids', [])
    if missing:
        fns_total += len(missing)
        for rid in missing:
            missing_rules[rid] = missing_rules.get(rid, 0) + 1
            print(f"- Missing {rid} in {case.get('name')} ({case.get('url')})")

print(f"\nTotal False Negatives: {fns_total}")
print("Rules missing (False Negatives):")
for rid, count in sorted(missing_rules.items(), key=lambda x: x[1], reverse=True):
    print(f" - {rid}: {count} occurrences")
