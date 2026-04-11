import json
from pathlib import Path

r = json.loads(Path('evaluation/phase12_post_upgrade_full1134_v5.json').read_text(encoding='utf-8'))

target_rules = ['avoid-inline-spacing','semantic-html','svg-no-accessible-name','aria-valid-attr-value','media-alternative','keyboard-trap','no-lang','empty-link','form-label-missing','empty-heading','link-purpose']

for rule in target_rules:
    print(f"\n## {rule}")
    shown = 0
    for c in r.get('cases', []):
        if c.get('skipped'):
            continue
        if rule not in set(c.get('missing_rule_ids', []) or []):
            continue
        print('url=', c.get('url'))
        for k in ['status','audit_status','engine','error','fetch_error','issues_count','predicted_rule_ids','expected_rule_ids','missing_rule_ids']:
            if k in c:
                v = c.get(k)
                if isinstance(v, list):
                    if k in {'predicted_rule_ids','expected_rule_ids','missing_rule_ids'}:
                        print(k, len(v), v[:10])
                    else:
                        print(k, len(v))
                else:
                    print(k, v)
        print('notes_keys', sorted([x for x in c.keys() if 'error' in x or 'status' in x or 'issue' in x]))
        shown += 1
        if shown >= 2:
            break
