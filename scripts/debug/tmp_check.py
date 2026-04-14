import json
with open('evaluation/benchmark_results.json') as f:
    d = json.load(f)
for c in d['cases']:
    if c['missing_rule_ids'] or c['unexpected_rule_ids']:
        print(f"{c['name']}:\n  Missed: {c['missing_rule_ids']}\n  Unexpected: {c['unexpected_rule_ids']}")
