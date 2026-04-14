import collections
import json
from pathlib import Path

path = Path('evaluation/retest_act_latest.json')
if not path.exists():
    raise SystemExit('missing evaluation/retest_act_latest.json')

data = json.loads(path.read_text(encoding='utf-8'))
cases = [c for c in data.get('cases', []) if not c.get('skipped')]

missing = collections.Counter()
for c in cases:
    missing.update(c.get('missing_rule_ids', []) or [])

metrics = data.get('metrics', {}) or {}
adj = data.get('adjudicated_metrics', {}) or {}

print('cases', len(cases))
print('micro_precision', metrics.get('precision'))
print('micro_recall', metrics.get('recall'))
print('micro_f1', metrics.get('f1'))
print('adj_precision', adj.get('precision'))
print('adj_recall', adj.get('recall'))
print('adj_f1', adj.get('f1'))

fn_total = 0
for c in cases:
    fn_total += len(c.get('missing_rule_ids', []) or [])
print('fn_total', fn_total)

print('top_missing')
for rid, cnt in missing.most_common(15):
    print(rid, cnt)
