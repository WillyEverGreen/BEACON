import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else 'evaluation/retest_act_latest.json'

with open(path, encoding='utf-8') as f:
    data = json.load(f)

for case in data.get('cases', []):
    expected = case.get('expected_rule_ids', [])
    activity = case.get('rule_activity', {}) or {}
    fired = sorted(
        [rid for rid, meta in activity.items() if isinstance(meta, dict) and int(meta.get('violations_found', 0) or 0) > 0]
    )
    print(f"{case.get('name')}: expected={expected}")
    print(f"  fired={fired}")
