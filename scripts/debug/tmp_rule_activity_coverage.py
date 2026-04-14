import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else 'evaluation/retest_act_latest.json'

with open(path, encoding='utf-8') as f:
    data = json.load(f)

cases = data.get('cases', [])

detected = 0
missing = 0
rows = []
for case in cases:
    expected = set(case.get('expected_rule_ids', []))
    activity = case.get('rule_activity', {}) or {}
    fired = {
        rid for rid, meta in activity.items()
        if isinstance(meta, dict) and int(meta.get('violations_found', 0) or 0) > 0
    }
    hit = expected & fired
    rows.append((case.get('name'), sorted(expected), sorted(hit), sorted(expected - fired)))
    if hit:
        detected += 1
    else:
        missing += 1

print(f'file: {path}')
print(f'cases with expected rule firing in rule_activity: {detected}/{len(cases)}')
for name, expected, hit, miss in rows:
    print(f"{name}: expected={expected} fired_hit={hit} unfired={miss}")
