import json
from pathlib import Path

d = json.loads(Path('evaluation/retest_act_latest.json').read_text(encoding='utf-8'))
cases = [c for c in d.get('cases', []) if not c.get('skipped')]

tp = fp = fn = 0
atp = afp = afn = 0
for c in cases:
    m = c.get('metrics', {}) or {}
    tp += int(m.get('tp', 0) or 0)
    fp += int(m.get('fp', 0) or 0)
    fn += int(m.get('fn', 0) or 0)

    am = c.get('adjudicated_metrics', {}) or {}
    atp += int(am.get('tp', 0) or 0)
    afp += int(am.get('fp', 0) or 0)
    afn += int(am.get('fn', 0) or 0)

prec = tp / (tp + fp) if (tp + fp) else 0.0
rec = tp / (tp + fn) if (tp + fn) else 0.0
f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0

aprec = atp / (atp + afp) if (atp + afp) else 0.0
arec = atp / (atp + afn) if (atp + afn) else 0.0
af1 = (2 * aprec * arec / (aprec + arec)) if (aprec + arec) else 0.0

print('tp', tp, 'fp', fp, 'fn', fn)
print('precision', round(prec * 100, 2), 'recall', round(rec * 100, 2), 'f1', round(f1 * 100, 2))
print('adj_tp', atp, 'adj_fp', afp, 'adj_fn', afn)
print('adj_precision', round(aprec * 100, 2), 'adj_recall', round(arec * 100, 2), 'adj_f1', round(af1 * 100, 2))
