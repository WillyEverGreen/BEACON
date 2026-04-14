import json
from pathlib import Path

r = json.loads(Path('evaluation/phase12_post_upgrade_full1134_v5.json').read_text(encoding='utf-8'))
rules = ['svg-no-accessible-name','keyboard-trap','link-purpose','empty-link','aria-valid-attr-value','semantic-html']
for rule in rules:
    print('\n###', rule)
    found = 0
    for c in r.get('cases', []):
        if c.get('skipped'):
            continue
        expected = set(c.get('expected_rule_ids', []) or [])
        predicted = set(c.get('predicted_rule_ids', []) or [])
        if rule in expected and rule in predicted:
            print('TP case:', c.get('url'), 'pred_count=', len(predicted))
            found += 1
            if found >= 3:
                break
    if found == 0:
        print('No TP sample found')
