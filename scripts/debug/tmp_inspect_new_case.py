import json
from pathlib import Path

path = Path('evaluation/phase_full_after_patch.json')
d = json.loads(path.read_text(encoding='utf-8'))
url = 'https://act-rules.github.io/testcases/efbfc7/9930d3f2863fb8d1a18b75a472ffad5348f5e306.html'
c = next((x for x in d.get('cases', []) if x.get('url') == url), None)
if not c:
    print('case not found')
    raise SystemExit(1)
print('pred', c.get('predicted_rule_ids'))
print('missing', c.get('missing_rule_ids'))
tele = c.get('precision_profile_telemetry', {})
print('issues_before', tele.get('issues_before_filtering'), 'after', tele.get('issues_after_filtering'))
ra = c.get('rule_activity', {})
for rule in ['text-spacing','letter-spacing','line-height','avoid-inline-spacing','media-alternative','form-label-missing','label','missing-label','input-label']:
    if rule in ra:
        info = ra[rule]
        print(rule, 'checked=', info.get('elements_checked'), 'viol=', info.get('violations_found'), 'status=', info.get('firing_status'))
    else:
        print(rule, 'missing in rule_activity')
