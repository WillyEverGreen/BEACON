import json

with open('evaluation/benchmark_cases_20.json', encoding='utf-8') as f:
    data = json.load(f)

for idx, case in enumerate(data.get('cases', [])):
    expected = case.get('expected_rule_ids', [])
    print(f"{idx}: expected={expected} url={case.get('url')}")
