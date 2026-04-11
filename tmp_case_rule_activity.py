import json
from pathlib import Path

r = json.loads(Path('evaluation/phase12_post_upgrade_full1134_v5.json').read_text(encoding='utf-8'))
urls = [
    'https://act-rules.github.io/testcases/7d6734/0fd9df3029d10e81ef1e453902e8f61670939b52.html',
    'https://act-rules.github.io/testcases/cc0f0a/0ed8074a5bee7052a1a28f9fd718b7d35a645cfd.html',
    'https://act-rules.github.io/testcases/efbfc7/9930d3f2863fb8d1a18b75a472ffad5348f5e306.html',
]
rules = ['svg-no-accessible-name','form-label-missing','input-label','input-name','missing-label','text-spacing','letter-spacing','avoid-inline-spacing','media-alternative','aria-valid-attr-value','semantic-html','keyboard-trap','no-lang','empty-link','link-purpose','aria-role','empty-heading','unsafe-external-link']

for u in urls:
    print('\n===', u)
    c = next((x for x in r.get('cases', []) if x.get('url') == u), None)
    if not c:
        print('not found')
        continue
    tele = c.get('precision_profile_telemetry', {}) or {}
    print('profile', tele.get('profile'))
    print('issues_before', tele.get('issues_before_filtering'), 'after', tele.get('issues_after_filtering'), 'reported', tele.get('reported_issues'))
    print('recovery', tele.get('recovery_applied'), 'fixture_like', tele.get('fixture_like_input'), 'recovery_reason', tele.get('recovery_reason'))
    print('scan_summary', c.get('scan_summary'))
    ra = c.get('rule_activity', {}) or {}
    print('rule_activity_count', len(ra))
    for rule in rules:
        v = ra.get(rule)
        if not v:
            continue
        print(rule, 'checked=', v.get('elements_checked'), 'viol=', v.get('violations_found'), 'status=', v.get('firing_status'))
    print('pred', c.get('predicted_rule_ids', [])[:20])
    print('expected', c.get('expected_rule_ids', [])[:20])
