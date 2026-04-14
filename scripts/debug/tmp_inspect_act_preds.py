import json

with open('evaluation/retest_act_latest.json', encoding='utf-8') as f:
    data = json.load(f)

for case in data.get('cases', []):
    preds = case.get('predicted_rule_ids', [])
    if preds:
        print(case.get('name'), 'preds=', preds, 'expected=', case.get('expected_rule_ids', []))
