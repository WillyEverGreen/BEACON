import collections
import json
from pathlib import Path

def load(path: str):
    return json.loads(Path(path).read_text(encoding='utf-8'))

old_path = 'evaluation/phase12_post_upgrade_full1134_v5.json'
new_path = 'evaluation/phase_full_after_patch.json'
old = load(old_path)
new = load(new_path)

def aggregate(data):
    cases = [c for c in data.get('cases', []) if not c.get('skipped')]
    tp = fp = fn = 0
    miss = collections.Counter()
    for c in cases:
        m = c.get('metrics', {}) or {}
        tp += int(m.get('tp', 0) or 0)
        fp += int(m.get('fp', 0) or 0)
        fn += int(m.get('fn', 0) or 0)
        miss.update(c.get('missing_rule_ids', []) or [])
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0
    return {
        'tp': tp, 'fp': fp, 'fn': fn,
        'precision': prec, 'recall': rec, 'f1': f1,
        'missing_total': sum(miss.values()),
        'missing_counter': miss,
        'cases': len(cases),
    }

o = aggregate(old)
n = aggregate(new)

print('OLD', o['cases'], o['tp'], o['fp'], o['fn'], round(o['precision']*100,2), round(o['recall']*100,2), round(o['f1']*100,2), o['missing_total'])
print('NEW', n['cases'], n['tp'], n['fp'], n['fn'], round(n['precision']*100,2), round(n['recall']*100,2), round(n['f1']*100,2), n['missing_total'])
print('DELTA_FN', n['fn'] - o['fn'])
print('DELTA_MISSING', n['missing_total'] - o['missing_total'])
print('TOP_MISSING_NEW')
for rid, cnt in n['missing_counter'].most_common(20):
    print(rid, cnt)
